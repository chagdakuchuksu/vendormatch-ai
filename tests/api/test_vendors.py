import pytest

from tests.api.conftest import vendor_payload


@pytest.fixture
def vendor(client, project):
    r = client.post(f"/api/projects/{project['id']}/vendors", json=vendor_payload())
    assert r.status_code == 201, r.text
    return r.json()


def test_create_vendor_persists_all_fields(client, project, vendor):
    assert vendor["project_id"] == project["id"] and vendor["is_demo"] is False
    for field, value in vendor_payload().items():
        assert vendor[field] == value
    assert client.get(f"/api/vendors/{vendor['id']}").json() == vendor


def test_list_vendors(client, project, vendor):
    second = client.post(f"/api/projects/{project['id']}/vendors", json=vendor_payload(name="Vendor B")).json()
    rows = client.get(f"/api/projects/{project['id']}/vendors").json()
    assert [v["id"] for v in rows] == [vendor["id"], second["id"]]


def test_vendor_optional_fields(client, project):
    r = client.post(f"/api/projects/{project['id']}/vendors", json={"name": "Minimal vendor"})
    assert r.status_code == 201
    v = r.json()
    assert (v["proposed_budget"], v["proposed_duration"], v["technologies"], v["proposal_text"]) == (None, None, [], "")


def test_update_vendor(client, vendor):
    r = client.put(f"/api/vendors/{vendor['id']}", json=vendor_payload(proposed_duration=26, duration_unit="weeks", technologies=["Flutter"]))
    assert r.status_code == 200
    body = r.json()
    assert (body["proposed_duration"], body["duration_unit"], body["technologies"]) == (26, "weeks", ["Flutter"])
    assert body["created_at"] == vendor["created_at"]
    assert client.get(f"/api/vendors/{vendor['id']}").json() == body


def test_delete_vendor(client, project, vendor):
    assert client.delete(f"/api/vendors/{vendor['id']}").status_code == 204
    assert client.get(f"/api/vendors/{vendor['id']}").status_code == 404
    assert client.get(f"/api/projects/{project['id']}/vendors").json() == []


@pytest.mark.parametrize(("method", "path"), [("get", "/api/vendors/999"), ("put", "/api/vendors/999"), ("delete", "/api/vendors/999")])
def test_missing_vendor_returns_404(client, method, path):
    kwargs = {"json": vendor_payload()} if method == "put" else {}
    r = getattr(client, method)(path, **kwargs)
    assert r.status_code == 404
    assert r.json()["error"]["details"] == {"vendor_id": 999}


@pytest.mark.parametrize("method", ["get", "post"])
def test_vendors_of_missing_project_404(client, method):
    kwargs = {"json": vendor_payload()} if method == "post" else {}
    r = getattr(client, method)("/api/projects/999/vendors", **kwargs)
    assert r.status_code == 404 and r.json()["error"]["details"] == {"project_id": 999}


@pytest.mark.parametrize(
    "overrides",
    [{"name": ""}, {"proposed_budget": -1}, {"proposed_duration": 0}, {"years_experience": -2},
     {"duration_unit": "days"}, {"technologies": "React Native"}, {"rating": 5}],
)
def test_invalid_vendor_input(client, project, overrides):
    r = client.post(f"/api/projects/{project['id']}/vendors", json=vendor_payload(**overrides))
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"
