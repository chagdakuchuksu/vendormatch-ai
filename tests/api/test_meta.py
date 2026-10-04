from app.config import Settings


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "scoring_version": "1.2"}


def test_scoring_model_exposes_constants(client):
    body = client.get("/api/scoring-model").json()
    assert body["scoring_version"] == "1.2"
    assert body["default_weights"] == {"critical": 4.0, "high": 3.0, "medium": 2.0, "low": 1.0}
    assert body["hard_fail_factors"] == {"critical": 0.5, "high": 0.6, "medium": 0.7, "low": 0.8}
    assert body["flexible_numeric"]["default_tolerance"] == 0.25
    sem = body["semantic"]
    assert (sem["lower_threshold"], sem["upper_threshold"], sem["provisional"], sem["runs_locally"]) == (0.3, 0.6, True, True)
    assert body["low_bid_concern"]["affects_score"] is False
    assert body["auto_criteria"]["technology"] == {"importance": "critical", "requirement_type": "hard", "flexibility": None}
    assert "overall_score" in body["formulas"]


def test_unknown_route_uses_error_shape(client):
    r = client.get("/api/nope")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_tests_use_a_temporary_database(client, tmp_path):
    settings = client.app.state.settings
    assert settings.db_path == tmp_path / "test.db"
    assert settings.db_path.exists()
    assert settings.db_path != Settings().db_path


def test_scoring_model_documents_duration_conversion(client):
    conv = client.get("/api/scoring-model").json()["duration_conversion"]
    assert conv["days_per_week"] == 7
    assert conv["days_per_month"].startswith("364/12")
    assert conv["examples"]["6 months"] == "182 days = 26 weeks"
