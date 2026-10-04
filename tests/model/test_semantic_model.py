"""Real all-MiniLM-L6-v2 tests. Opt-in:  pytest -m model

They load the local model (downloaded once from the Hugging Face Hub, then cached) and are
skipped if sentence-transformers or the model is unavailable. Assertions are deliberately
about orderings and broad bands, not exact similarity values.
"""

import json
from pathlib import Path

import pytest

from app.config import DEFAULT_SCORING_CONFIG as CFG
from app.schemas.enums import CriterionKind, CriterionStatus
from app.services.scoring.text import SemanticCriterionScorer
from app.services.semantic.matcher import cosine_similarity
from tests.helpers import criterion, vendor

pytestmark = pytest.mark.model

PAIRS = json.loads((Path(__file__).resolve().parents[2] / "calibration" / "semantic_pairs.json").read_text("utf-8"))["pairs"]


@pytest.fixture(scope="module")
def embedder():
    pytest.importorskip("sentence_transformers")
    from app.services.semantic.embedder import SentenceTransformerEmbedder

    emb = SentenceTransformerEmbedder()
    try:
        emb.encode(["warm-up"])
    except Exception as exc:  # model not downloadable/available offline
        pytest.skip(f"MiniLM model unavailable: {exc}")
    return emb


def sim(embedder, a, b):
    va, vb = embedder.encode([a, b])
    return cosine_similarity(va, vb)


def by_category(embedder, category):
    return [sim(embedder, p["requirement"], p["evidence"]) for p in PAIRS if p["category"] == category]


def test_spec_examples_are_recognized(embedder):
    retail = sim(embedder, "Previous e-commerce experience", "We have developed six online retail platforms for European customers.")
    payments = sim(embedder, "Payment integration experience", "We integrated Stripe, PayPal and Adyen into several online stores.")
    assert retail > CFG.semantic_lower
    assert payments > CFG.semantic_lower


def test_unrelated_pairs_score_no_match(embedder):
    assert all(s <= CFG.semantic_lower for s in by_category(embedder, "unrelated"))


def test_every_strong_pair_beats_every_unrelated_pair(embedder):
    assert min(by_category(embedder, "strong")) > max(by_category(embedder, "unrelated"))


def test_strong_pairs_average_above_partial_pairs(embedder):
    strong, partial = by_category(embedder, "strong"), by_category(embedder, "partial")
    assert sum(strong) / len(strong) > sum(partial) / len(partial)


def test_scorer_picks_the_relevant_sentence(embedder):
    c = criterion(CriterionKind.TEXT, name="E-commerce", description="Previous e-commerce experience")
    v = vendor(
        proposal_text=(
            "Our office is in Lisbon and we have 40 employees. "
            "We have developed six online retail platforms for European customers. "
            "Our team enjoys hiking."
        )
    )
    r = SemanticCriterionScorer(embedder)(c, v, CFG)
    assert r.evidence.matched_text == "We have developed six online retail platforms for European customers."
    assert r.status in (CriterionStatus.PASS, CriterionStatus.WARNING)


def test_similarities_are_deterministic(embedder):
    a = sim(embedder, PAIRS[0]["requirement"], PAIRS[0]["evidence"])
    embedder._cache.clear()
    b = sim(embedder, PAIRS[0]["requirement"], PAIRS[0]["evidence"])
    assert a == pytest.approx(b, abs=1e-5)


def test_demo_with_real_model(embedder, tmp_path):
    """The fictional demo, analyzed with real MiniLM through the API and a temporary database."""
    from fastapi.testclient import TestClient

    from app.config import PROJECT_ROOT, Settings
    from app.main import create_app

    app = create_app(Settings(db_path=tmp_path / "demo.db", examples_dir=PROJECT_ROOT / "examples"),
                     semantic_scorer=SemanticCriterionScorer(embedder))
    with TestClient(app) as client:
        pid = client.post("/api/demo").json()["project_id"]
        vendors = {v["vendor_name"]: v for v in client.get(f"/api/projects/{pid}/analysis").json()["vendors"]}
    harbor = vendors["Harborline Software (fictional)"]
    kestrel = vendors["Kestrel Mobile Labs (fictional)"]
    quill = vendors["Quillstone Digital (fictional)"]
    assert harbor["overall_score"] > quill["overall_score"] > kestrel["overall_score"]
    assert 85 <= harbor["overall_score"] < 100
    assert harbor["compatibility_label"] == "Strong compatibility"
    assert kestrel["compatibility_label"] == "Hard requirement failed"
    assert quill["hard_requirements_met"] is True

    def evidence(vendor, name):
        return next(c for c in vendor["criteria"] if c["name"] == name)["evidence"]

    ecom = evidence(harbor, "E-commerce experience")
    assert ecom["strength"] == "strong"
    assert ecom["matched_text"].startswith("We have extensive e-commerce experience")
    # The balanced vendor has only limited, moderately related e-commerce evidence.
    assert evidence(quill, "E-commerce experience")["strength"] == "partial"
    assert evidence(quill, "E-commerce experience")["similarity"] < ecom["similarity"]
