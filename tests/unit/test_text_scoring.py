"""SemanticCriterionScorer with fake embedders: explainability, statuses and isolation."""

import dataclasses

import pytest

from app.config import DEFAULT_SCORING_CONFIG as CFG
from app.config import ScoringConfig
from app.schemas.enums import CriterionKind, CriterionStatus
from app.services.criteria_builder import build_criteria
from app.services.scoring.engine import evaluate_vendor
from app.services.scoring.text import SemanticCriterionScorer
from tests.fakes import ConstantSimilarityEmbedder, TableEmbedder, unit_vector_with_cosine
from tests.helpers import criterion, spec_example_project, vendor

REQ = "Previous e-commerce experience"


def text_criterion(**kw):
    kw.setdefault("description", REQ)
    kw.setdefault("name", "E-commerce experience")
    return criterion(CriterionKind.TEXT, **kw)


def score_with_similarity(sim, **crit_kw):
    v = vendor(proposal_text="We have developed six online retail platforms.")
    return SemanticCriterionScorer(ConstantSimilarityEmbedder(sim))(text_criterion(**crit_kw), v, CFG)


# --- statuses and explainability ------------------------------------------------------------

def test_strong_match_result_is_fully_explained():
    r = score_with_similarity(0.72)
    assert (r.score, r.status, r.hard_failure) == (1.0, CriterionStatus.PASS, False)
    e = r.evidence
    assert e.requirement_text == REQ
    assert e.matched_text == "We have developed six online retail platforms."
    assert e.source == "proposal"
    assert e.similarity == pytest.approx(0.72)
    assert e.normalized_score == 1.0
    assert e.strength == "strong"
    assert (e.lower_threshold, e.upper_threshold) == (0.30, 0.60)
    assert r.summary == "Strong semantic match (0.72)"
    assert '"We have developed six online retail platforms."' in r.explanation
    assert "cosine similarity 0.72" in r.explanation
    assert "provisional thresholds" in r.explanation


def test_partial_match_is_linearly_scaled():
    r = score_with_similarity(0.45)
    assert r.score == pytest.approx(0.5)
    assert r.evidence.normalized_score == pytest.approx(0.5)
    assert r.status == CriterionStatus.WARNING
    assert r.summary == "Partial semantic match (0.45)"


def test_no_semantic_match_soft_fails_without_penalty():
    r = score_with_similarity(0.12)
    assert (r.score, r.status, r.hard_failure) == (0.0, CriterionStatus.FAIL, False)
    assert r.evidence.strength == "none"
    assert r.evidence.matched_text  # closest sentence is still shown
    assert "Closest sentence" in r.explanation
    assert r.summary == "No relevant evidence found (0.12)"


def test_no_semantic_match_on_hard_text_criterion_is_hard_failure():
    r = score_with_similarity(0.12, requirement_type="hard", importance="high")
    assert r.hard_failure and r.penalty_factor == 0.6


def test_custom_thresholds_from_config():
    cfg = dataclasses.replace(CFG, semantic_lower=0.1, semantic_upper=0.3)
    v = vendor(proposal_text="Anything at all.")
    r = SemanticCriterionScorer(ConstantSimilarityEmbedder(0.2))(text_criterion(), v, cfg)
    assert r.score == pytest.approx(0.5)


def test_invalid_config_thresholds_rejected():
    with pytest.raises(ValueError):
        ScoringConfig(semantic_lower=0.6, semantic_upper=0.3)


def test_best_sentence_across_proposal_and_previous_projects():
    table = {
        REQ: [1.0, 0.0],
        "We are a team of twelve.": unit_vector_with_cosine(0.05),
        "We value clean code.": unit_vector_with_cosine(0.20),
        "Built a webshop for a shoe brand.": unit_vector_with_cosine(0.66),
    }
    v = vendor(
        proposal_text="We are a team of twelve. We value clean code.",
        previous_projects=["Built a webshop for a shoe brand."],
    )
    r = SemanticCriterionScorer(TableEmbedder(table))(text_criterion(), v, CFG)
    assert r.evidence.matched_text == "Built a webshop for a shoe brand."
    assert r.evidence.source == "previous project 1"
    assert r.evidence.similarity == pytest.approx(0.66)
    assert r.vendor_value == "Built a webshop for a shoe brand."


@pytest.mark.parametrize(("requirement_type", "hard"), [("soft", False), ("hard", True)])
def test_no_proposal_text_is_missing(requirement_type, hard):
    emb = ConstantSimilarityEmbedder(0.9)
    r = SemanticCriterionScorer(emb)(text_criterion(requirement_type=requirement_type), vendor(), CFG)
    assert (r.score, r.status, r.evidence) == (0.0, CriterionStatus.MISSING, None)
    assert r.hard_failure is hard
    assert emb.calls == []  # nothing to embed


def test_rejects_non_text_criteria():
    scorer = SemanticCriterionScorer(ConstantSimilarityEmbedder(0.9))
    with pytest.raises(ValueError, match="only applies to 'text'"):
        scorer(criterion(CriterionKind.TECHNOLOGY, technology="Go"), vendor(proposal_text="Go."), CFG)


# --- isolation from structured scoring ------------------------------------------------------

TECHS = ["React Native", "Node.js", "PostgreSQL"]


def structured(analysis):
    return [r.model_dump() for r in analysis.criteria if r.kind != CriterionKind.TEXT]


@pytest.fixture
def spec():
    p = spec_example_project()
    return p, build_criteria(p)


def test_semantic_results_never_change_structured_criteria(spec):
    p, crits = spec
    v = vendor(proposed_budget=55_000, proposed_duration=8, years_experience=4, technologies=["Flutter"],
               proposal_text="We built online shops with React Native and PostgreSQL.")
    runs = [evaluate_vendor(p, crits, v, semantic_scorer=SemanticCriterionScorer(ConstantSimilarityEmbedder(s)))
            for s in (-0.2, 0.1, 0.45, 0.99)]
    baseline = structured(runs[0])
    assert all(structured(r) == baseline for r in runs[1:])
    assert {r.overall_score for r in runs} != {runs[0].overall_score}  # only the text criterion moved


def test_semantic_match_cannot_rescue_hard_failure(spec):
    p, crits = spec
    v = vendor(proposed_budget=40_000, proposed_duration=8, years_experience=10, technologies=TECHS,
               proposal_text="We delivered ten e-commerce apps on time.")
    a = evaluate_vendor(p, crits, v, semantic_scorer=SemanticCriterionScorer(ConstantSimilarityEmbedder(1.0)))
    assert not a.hard_requirements_met
    assert a.status_label == "Hard requirement failed: Duration"
    assert a.hard_penalty_factor == 0.5


def test_embedder_only_sees_text_criteria(spec):
    p, crits = spec
    emb = ConstantSimilarityEmbedder(0.7)
    v = vendor(proposed_budget=50_000, proposed_duration=6, years_experience=6, technologies=TECHS,
               proposal_text="Six online retail platforms. Stripe integrations.")
    evaluate_vendor(p, crits, v, semantic_scorer=SemanticCriterionScorer(emb))
    text_reqs = [c.description for c in crits if c.kind == CriterionKind.TEXT]
    assert [call[0] for call in emb.calls] == text_reqs
