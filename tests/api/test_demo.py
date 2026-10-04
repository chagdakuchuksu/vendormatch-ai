from app.config import PROJECT_ROOT
from app.services.demo_service import read_demo_data
from tests.fakes import ConstantSimilarityEmbedder

HARBORLINE = "Harborline Software (fictional)"
KESTREL = "Kestrel Mobile Labs (fictional)"
QUILLSTONE = "Quillstone Digital (fictional)"


def load(client):
    r = client.post("/api/demo")
    assert r.status_code == 201, r.text
    return r.json()


def by_name(items, key="vendor_name"):
    return {i[key]: i for i in items}


def crit(vendor, name):
    return next(c for c in vendor["criteria"] if c["name"] == name)


def test_demo_files_are_valid_and_fictional():
    demo = read_demo_data(PROJECT_ROOT / "examples")
    assert "fictional" in demo.project.name.lower()
    assert len(demo.vendors) >= 3
    assert all("(fictional)" in v.name for v in demo.vendors)


def test_load_demo(client):
    body = load(client)
    assert body["fictional"] is True and "fictional" in body["notice"]
    project = client.get(f"/api/projects/{body['project_id']}").json()
    assert project["is_demo"] is True
    vendors = client.get(f"/api/projects/{body['project_id']}/vendors").json()
    assert [v["id"] for v in vendors] == body["vendor_ids"]
    assert all(v["is_demo"] for v in vendors)
    assert set(by_name(vendors, "name")) == {HARBORLINE, KESTREL, QUILLSTONE}


def test_demo_analysis_demonstrates_key_behaviours(make_client):
    client = make_client(ConstantSimilarityEmbedder(0.9))
    pid = load(client)["project_id"]
    vendors = by_name(client.get(f"/api/projects/{pid}/analysis").json()["vendors"])

    harbor, kestrel, quill = vendors[HARBORLINE], vendors[KESTREL], vendors[QUILLSTONE]
    # Over the flexible budget, but all hard requirements met and competitive.
    assert harbor["hard_requirements_met"] is True
    assert crit(harbor, "Budget")["status"] == "warning"
    # Strict duration violated -> hard failure, still listed.
    assert kestrel["hard_requirements_met"] is False
    assert kestrel["status_label"] == "Hard requirement failed: Duration"
    # Different technology matches: soft PostgreSQL preference missed, experience below minimum.
    assert crit(quill, "PostgreSQL")["status"] == "fail" and not crit(quill, "PostgreSQL")["hard_failure"]
    assert quill["technology_coverage"] < 1 and harbor["technology_coverage"] == 1
    assert crit(quill, "Company experience")["status"] == "warning"
    # Different final scores, flexible-budget vendor ahead of the deadline violator.
    scores = [v["overall_score"] for v in vendors.values()]
    assert len(set(scores)) == 3
    assert harbor["overall_score"] > kestrel["overall_score"]
    assert quill["overall_score"] > kestrel["overall_score"]


def test_demo_uses_semantic_criteria(client):
    pid = load(client)["project_id"]
    harbor = by_name(client.get(f"/api/projects/{pid}/analysis").json()["vendors"])[HARBORLINE]
    for name in ("E-commerce experience", "Payment integration"):
        c = crit(harbor, name)
        assert c["kind"] == "text" and c["evidence"]["matched_text"]


def test_repeated_demo_loading_is_deterministic(client):
    first, second = load(client), load(client)
    assert first["project_id"] != second["project_id"]

    def content(pid):
        p = client.get(f"/api/projects/{pid}").json()
        return {k: v for k, v in p.items() if k not in ("id", "created_at", "updated_at")}

    assert content(first["project_id"]) == content(second["project_id"])

    def scores(pid):
        return [(v["vendor_name"], v["overall_score"]) for v in client.get(f"/api/projects/{pid}/analysis").json()["vendors"]]

    assert scores(first["project_id"]) == scores(second["project_id"])


def test_old_demo_copies_are_pruned(make_client):
    client = make_client(max_demo_projects=2)
    user_project = client.post("/api/projects", json={"name": "Mine", "budget": 1000}).json()
    ids = [load(client)["project_id"] for _ in range(4)]
    remaining = {p["id"] for p in client.get("/api/projects").json()}
    assert remaining == {user_project["id"], ids[2], ids[3]}  # user projects are never pruned
