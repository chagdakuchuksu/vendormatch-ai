"""Production configuration: env settings, model preloading, container files."""

import re

from fastapi.testclient import TestClient

from app.config import DEFAULT_SCORING_CONFIG, PROJECT_ROOT, Settings
from app.main import create_app
from app.services.scoring.text import SemanticCriterionScorer
from tests.fakes import BagOfWordsEmbedder


class CountingEmbedder(BagOfWordsEmbedder):
    def __init__(self, fail=False):
        super().__init__()
        self.warm_ups = 0
        self.fail = fail

    def warm_up(self):
        self.warm_ups += 1
        if self.fail:
            raise RuntimeError("model unavailable")


def run_app(tmp_path, embedder, preload):
    settings = Settings(db_path=tmp_path / "p.db", examples_dir=PROJECT_ROOT / "examples", preload_model=preload)
    with TestClient(create_app(settings, semantic_scorer=SemanticCriterionScorer(embedder))) as client:
        return client.get("/api/health").status_code


def test_settings_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("VENDORMATCH_DB_PATH", str(tmp_path / "x.db"))
    monkeypatch.setenv("VENDORMATCH_PRELOAD_MODEL", "1")
    monkeypatch.setenv("VENDORMATCH_MAX_DEMO_PROJECTS", "3")
    s = Settings.from_env()
    assert (s.db_path, s.preload_model, s.max_demo_projects) == (tmp_path / "x.db", True, 3)


def test_preload_off_by_default(monkeypatch):
    monkeypatch.delenv("VENDORMATCH_PRELOAD_MODEL", raising=False)
    assert Settings.from_env().preload_model is False


def test_model_preloaded_once_at_startup(tmp_path):
    emb = CountingEmbedder()
    assert run_app(tmp_path, emb, preload=True) == 200
    assert emb.warm_ups == 1


def test_no_preload_when_disabled(tmp_path):
    emb = CountingEmbedder()
    run_app(tmp_path, emb, preload=False)
    assert emb.warm_ups == 0


def test_failed_preload_does_not_stop_the_app(tmp_path):
    assert run_app(tmp_path, CountingEmbedder(fail=True), preload=True) == 200


def test_dockerfile_bakes_the_configured_model():
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    model = re.search(r"^ARG MODEL_NAME=(\S+)$", dockerfile, re.M).group(1)
    assert model == DEFAULT_SCORING_CONFIG.semantic_model_name
    assert "HF_HUB_OFFLINE=1" in dockerfile and "${PORT}" in dockerfile
    assert "VENDORMATCH_PRELOAD_MODEL=1" in dockerfile


def test_dockerignore_keeps_runtime_files():
    lines = (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    ignored = [line.strip() for line in lines if line.strip() and not line.startswith("#")]
    for needed in ("app", "static", "examples", "requirements.txt"):
        assert needed not in ignored
