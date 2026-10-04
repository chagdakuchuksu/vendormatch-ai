"""API test fixtures: every test gets its own temporary SQLite file and a fake embedder."""

import pytest
from fastapi.testclient import TestClient

from app.config import PROJECT_ROOT, Settings
from app.main import create_app
from app.services.scoring.text import SemanticCriterionScorer
from tests.fakes import BagOfWordsEmbedder


@pytest.fixture
def make_client(tmp_path):
    clients = []

    def _make(embedder=None, **settings_overrides):
        settings = Settings(
            db_path=tmp_path / "test.db",
            examples_dir=PROJECT_ROOT / "examples",
            **settings_overrides,
        )
        app = create_app(settings, semantic_scorer=SemanticCriterionScorer(embedder or BagOfWordsEmbedder()))
        client = TestClient(app)
        client.__enter__()  # runs the lifespan (creates the schema in the temp DB)
        clients.append(client)
        return client

    yield _make
    for c in clients:
        c.__exit__(None, None, None)


@pytest.fixture
def client(make_client):
    return make_client()


# --- payload builders -----------------------------------------------------------------------

def spec_project_payload(**overrides) -> dict:
    payload = {
        "name": "E-commerce Mobile Application",
        "description": "Fictional test project.",
        "budget": 50000,
        "currency": "EUR",
        "max_duration": 6,
        "duration_unit": "months",
        "required_technologies": ["React Native", "Node.js", "PostgreSQL"],
        "criteria": [
            {"name": "Duration", "kind": "duration", "importance": "critical", "requirement_type": "hard", "flexibility": "strict"},
            {"name": "Budget", "kind": "budget", "importance": "high", "requirement_type": "soft", "flexibility": "flexible"},
            {"name": "React Native", "kind": "technology", "technology": "React Native", "importance": "critical", "requirement_type": "hard"},
            {"name": "E-commerce experience", "kind": "text", "description": "Previous e-commerce experience", "importance": "high", "requirement_type": "soft"},
            {"name": "Company experience", "kind": "experience", "min_value": 5, "importance": "medium", "requirement_type": "soft", "flexibility": "flexible"},
        ],
    }
    payload.update(overrides)
    return payload


TECHS = ["React Native", "Node.js", "PostgreSQL"]


def vendor_payload(**overrides) -> dict:
    payload = {
        "name": "Vendor A (fictional)",
        "proposed_budget": 55000,
        "proposed_duration": 5,
        "duration_unit": "months",
        "years_experience": 8,
        "technologies": TECHS,
        "proposal_text": "We have developed six online retail platforms for European customers.",
        "previous_projects": ["Mobile shop for a fictional bakery."],
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def project(client) -> dict:
    r = client.post("/api/projects", json=spec_project_payload())
    assert r.status_code == 201, r.text
    return r.json()
