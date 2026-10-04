import pytest

from tests.api.conftest import spec_project_payload, vendor_payload


def by_name(project):
    return {c["name"]: c for c in project["criteria"]}


# --- create / read --------------------------------------------------------------------------

def test_create_project_materializes_criteria(client):
    r = client.post("/api/projects", json=spec_project_payload())
    assert r.status_code == 201
    p = r.json()
    assert p["id"] > 0 and p["is_demo"] is False
    crits = by_name(p)
    assert set(crits) == {"Duration", "Budget", "React Native", "E-commerce experience", "Company experience", "Node.js", "PostgreSQL"}
    assert crits["Node.js"]["source"] == "auto"
    assert (crits["Node.js"]["importance"], crits["Node.js"]["requirement_type"]) == ("critical", "hard")
    assert sum(c["normalized_weight"] for c in p["criteria"]) == pytest.approx(1.0)
    assert crits["Duration"]["normalized_weight"] == pytest.approx(4 / 24)


def test_get_project_persists_all_fields(client, project):
    got = client.get(f"/api/projects/{project['id']}").json()
    assert got == project
    for field in ("name", "description", "budget", "currency", "max_duration", "duration_unit", "required_technologies"):
        assert got[field] == spec_project_payload()[field]
    crit = by_name(got)["Company experience"]
    assert (crit["kind"], crit["min_value"], crit["flexibility"], crit["weight_source"]) == ("experience", 5, "flexible", "importance_default")


def test_list_projects(client, project):
    client.post(f"/api/projects/{project['id']}/vendors", json=vendor_payload())
    rows = client.get("/api/projects").json()
    assert len(rows) == 1
    assert rows[0]["id"] == project["id"]
    assert rows[0]["vendor_count"] == 1
    assert rows[0]["criteria_count"] == 7


# --- update ---------------------------------------------------------------------------------

def test_update_round_trip_allows_editing_auto_criteria(client, project):
    payload = {k: project[k] for k in spec_project_payload()}
    for c in payload["criteria"]:
        if c["name"] == "PostgreSQL":
            c["requirement_type"], c["importance"] = "soft", "medium"
    r = client.put(f"/api/projects/{project['id']}", json=payload)
    assert r.status_code == 200, r.text
    updated = r.json()
    pg = by_name(updated)["PostgreSQL"]
    assert (pg["requirement_type"], pg["importance"], pg["source"]) == ("soft", "medium", "auto")
    assert [c["id"] for c in updated["criteria"]] == [c["id"] for c in project["criteria"]]  # ids stable
    assert sum(c["normalized_weight"] for c in updated["criteria"]) == pytest.approx(1.0)
    assert pg["normalized_weight"] == pytest.approx(2 / 22)  # weights recomputed, not taken from input
    assert client.get(f"/api/projects/{project['id']}").json() == updated


def test_update_replaces_fields(client, project):
    r = client.put(f"/api/projects/{project['id']}", json=spec_project_payload(name="Renamed", budget=60000, required_technologies=["React Native"]))
    assert r.status_code == 200
    body = r.json()
    assert (body["name"], body["budget"]) == ("Renamed", 60000)
    assert "Node.js" not in by_name(body)
    assert body["updated_at"] >= body["created_at"]


# --- delete ---------------------------------------------------------------------------------

def test_delete_project_cascades_to_vendors(client, project):
    vendor = client.post(f"/api/projects/{project['id']}/vendors", json=vendor_payload()).json()
    assert client.delete(f"/api/projects/{project['id']}").status_code == 204
    assert client.get(f"/api/projects/{project['id']}").status_code == 404
    assert client.get(f"/api/vendors/{vendor['id']}").status_code == 404


# --- missing project ------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/projects/999"),
        ("put", "/api/projects/999"),
        ("delete", "/api/projects/999"),
        ("get", "/api/projects/999/analysis"),
        ("get", "/api/projects/999/comparison"),
    ],
)
def test_missing_project_returns_404(client, method, path):
    kwargs = {"json": spec_project_payload()} if method == "put" else {}
    r = getattr(client, method)(path, **kwargs)
    assert r.status_code == 404
    err = r.json()["error"]
    assert err["code"] == "not_found" and err["details"] == {"project_id": 999}


# --- invalid input --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "overrides",
    [
        {"name": ""},
        {"budget": -10},
        {"currency": "euro"},
        {"max_duration": 0},
        {"duration_unit": "years"},
        {"unexpected": "field"},
        {"required_technologies": ["  "]},
    ],
)
def test_invalid_project_input(client, overrides):
    r = client.post("/api/projects", json=spec_project_payload(**overrides))
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "validation_error" and err["details"]["errors"]


def test_non_integer_id_is_validation_error(client):
    assert client.get("/api/projects/abc").status_code == 422


# --- criteria validation --------------------------------------------------------------------

@pytest.mark.parametrize(
    "criterion",
    [
        {"name": "B", "kind": "budget"},  # missing flexibility
        {"name": "T", "kind": "technology", "technology": "Go", "flexibility": "strict"},
        {"name": "E", "kind": "experience", "flexibility": "flexible"},  # missing min_value
        {"name": "X", "kind": "text"},  # missing description
        {"name": "W", "kind": "text", "description": "d", "weight": -1},
        {"name": "K", "kind": "magic"},
    ],
)
def test_invalid_criterion_fields(client, criterion):
    r = client.post("/api/projects", json=spec_project_payload(criteria=[criterion]))
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_budget_criterion_without_project_budget(client):
    payload = spec_project_payload(budget=None)
    r = client.post("/api/projects", json=payload)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_criteria"


def test_duplicate_technology_criteria(client):
    crit = [{"name": "PG", "kind": "technology", "technology": "Postgres"}, {"name": "PG2", "kind": "technology", "technology": "postgresql"}]
    r = client.post("/api/projects", json=spec_project_payload(criteria=crit, required_technologies=[]))
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_criteria"


def test_all_zero_weights(client):
    payload = spec_project_payload(budget=None, max_duration=None, required_technologies=[],
                                   criteria=[{"name": "A", "kind": "text", "description": "a", "weight": 0}])
    r = client.post("/api/projects", json=payload)
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_weights"


def test_project_without_any_criteria(client):
    r = client.post("/api/projects", json={"name": "Empty"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_criteria"


def test_failed_update_leaves_project_unchanged(client, project):
    r = client.put(f"/api/projects/{project['id']}", json=spec_project_payload(budget=None))
    assert r.status_code == 422
    assert client.get(f"/api/projects/{project['id']}").json() == project
