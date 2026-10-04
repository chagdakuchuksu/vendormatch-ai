"""M4: the polished demo scenario, the comparison payload, neutrality and isolation.

Semantic scores are fixed with ConstantSimilarityEmbedder so the expected numbers are exact;
the real-model behaviour of the same demo is covered in tests/model/.
"""

import pytest

from tests.api.conftest import spec_project_payload, vendor_payload
from tests.fakes import ConstantSimilarityEmbedder

HARBORLINE = "Harborline Software (fictional)"
KESTREL = "Kestrel Mobile Labs (fictional)"
QUILLSTONE = "Quillstone Digital (fictional)"
FORBIDDEN = ("choose", "recommend", "best", "winner", "select", "hire", "should")

EXPECTED_CRITERIA = [
    # name, kind, importance, requirement_type, flexibility
    ("Duration", "duration", "critical", "hard", "strict"),
    ("Budget", "budget", "high", "soft", "flexible"),
    ("React Native", "technology", "critical", "hard", None),
    ("Node.js", "technology", "critical", "hard", None),
    ("PostgreSQL", "technology", "high", "soft", None),
    ("E-commerce experience", "text", "high", "soft", None),
    ("Payment integration", "text", "medium", "soft", None),
    ("Company experience", "experience", "medium", "soft", "flexible"),
]


@pytest.fixture
def client(make_client):
    return make_client(ConstantSimilarityEmbedder(0.9))  # every text criterion: strong match


@pytest.fixture
def demo(client):
    r = client.post("/api/demo")
    assert r.status_code == 201
    return r.json()


def get(client, path):
    r = client.get(path)
    assert r.status_code == 200, r.text
    return r.json()


def vendors_by_name(analysis):
    return {v["vendor_name"]: v for v in analysis["vendors"]}


def crit(vendor, name):
    return next(c for c in vendor["criteria"] if c["name"] == name)


# --- demo structure -------------------------------------------------------------------------

def test_exact_demo_project_structure(client, demo):
    p = get(client, f"/api/projects/{demo['project_id']}")
    assert p["name"] == "E-commerce Mobile Application (fictional demo)"
    assert (p["budget"], p["currency"], p["max_duration"], p["duration_unit"]) == (50000, "EUR", 6, "months")
    assert p["required_technologies"] == ["React Native", "Node.js", "PostgreSQL"]
    assert [(c["name"], c["kind"], c["importance"], c["requirement_type"], c["flexibility"]) for c in p["criteria"]] == EXPECTED_CRITERIA
    assert all(c["source"] == "user" for c in p["criteria"])  # every requirement is explicit
    weights = {c["name"]: c["normalized_weight"] for c in p["criteria"]}
    assert sum(weights.values()) == pytest.approx(1)
    assert weights["Duration"] == pytest.approx(4 / 25) and weights["Payment integration"] == pytest.approx(2 / 25)


def test_exactly_three_fictional_vendors(client, demo):
    vendors = get(client, f"/api/projects/{demo['project_id']}/vendors")
    assert [v["name"] for v in vendors] == [HARBORLINE, KESTREL, QUILLSTONE]
    assert all(v["is_demo"] and "(fictional)" in v["name"] and "fictional" in v["proposal_text"] for v in vendors)
    assert set(demo["vendor_profiles"]) == {HARBORLINE, KESTREL, QUILLSTONE}


# --- behaviours -----------------------------------------------------------------------------

def test_flexible_budget_warning_keeps_vendor_competitive(client, demo):
    h = vendors_by_name(get(client, f"/api/projects/{demo['project_id']}/analysis"))[HARBORLINE]
    b = crit(h, "Budget")
    # €54,500 vs €50,000: d = 0.09 -> s = 1 - (0.09 / 0.25)^2 = 0.8704
    assert (b["status"], b["hard_failure"]) == ("warning", False)
    assert b["score"] == pytest.approx(0.8704)
    assert b["summary"] == "€4,500 over budget"
    assert h["hard_requirements_met"] is True
    assert h["overall_score"] == 98.4 and h["overall_score"] < 100
    assert h["compatibility_label"] == "Strong compatibility"


def test_strict_duration_failure_applies_multiplier(client, demo):
    k = vendors_by_name(get(client, f"/api/projects/{demo['project_id']}/analysis"))[KESTREL]
    d = crit(k, "Duration")
    assert (d["status"], d["score"], d["hard_failure"], d["penalty_factor"]) == ("fail", 0.0, True, 0.5)
    assert d["summary"] == "2 months over the strict deadline"
    assert (k["base_score"], k["hard_penalty_factor"], k["overall_score"]) == (84.0, 0.5, 42.0)
    assert k["compatibility_label"] == "Hard requirement failed"
    assert k["missing_requirements"] == ["Duration"]
    assert crit(k, "Budget")["summary"] == "€12,000 under budget"  # cheapest, but that cannot offset the hard failure


def test_technology_matching_and_soft_gap(client, demo):
    q = vendors_by_name(get(client, f"/api/projects/{demo['project_id']}/analysis"))[QUILLSTONE]
    pg = crit(q, "PostgreSQL")
    assert (pg["status"], pg["hard_failure"], pg["vendor_value"]) == ("fail", False, "not listed")
    assert crit(q, "React Native")["status"] == crit(q, "Node.js")["status"] == "pass"
    assert q["technology_coverage"] == pytest.approx(2 / 3)
    assert crit(q, "Company experience")["status"] == "warning"
    assert q["missing_requirements"] == ["PostgreSQL"]
    # 100 - 12 (PostgreSQL) - 5.12 (experience 4 vs 5 years, flexible) = 82.88
    assert q["overall_score"] == 82.9 and q["hard_requirements_met"] is True


def test_semantic_evidence_comes_from_the_vendor_proposal(client, demo):
    analysis = get(client, f"/api/projects/{demo['project_id']}/analysis")
    vendors = {v["name"]: v for v in get(client, f"/api/projects/{demo['project_id']}/vendors")}
    for v in analysis["vendors"]:
        source = vendors[v["vendor_name"]]
        corpus = source["proposal_text"] + " ".join(source["previous_projects"])
        for name in ("E-commerce experience", "Payment integration"):
            ev = crit(v, name)["evidence"]
            assert ev["matched_text"] in corpus
            assert ev["requirement_text"] in ("Previous e-commerce experience", "Payment integration experience")
            assert {"similarity", "normalized_score", "strength"} <= set(ev)


def test_every_criterion_is_explained(client, demo):
    for v in get(client, f"/api/projects/{demo['project_id']}/analysis")["vendors"]:
        assert len(v["criteria"]) == 8
        for c in v["criteria"]:
            for field in ("required_value", "vendor_value", "score", "status", "normalized_weight",
                          "max_points", "contribution", "points_lost", "summary", "explanation"):
                assert c[field] not in (None, ""), (v["vendor_name"], c["name"], field)
        assert v["score_explanation"] and v["summary"]


# --- comparison -----------------------------------------------------------------------------

def test_comparison_ordering_and_note(client, demo):
    comp = get(client, f"/api/projects/{demo['project_id']}/comparison")
    assert [(r["vendor_name"], r["overall_score"]) for r in comp["rows"]] == [
        (HARBORLINE, 98.4), (QUILLSTONE, 82.9), (KESTREL, 42.0),
    ]
    assert "sorting aid, not a decision" in comp["ordering_note"]
    assert "Decision support only" in comp["disclaimer"]


def test_comparison_columns(client, demo):
    comp = get(client, f"/api/projects/{demo['project_id']}/comparison")
    assert [c["name"] for c in comp["criteria"]] == [c[0] for c in EXPECTED_CRITERIA]
    assert sum(c["max_points"] for c in comp["criteria"]) == pytest.approx(100)
    assert comp["criteria"][0]["required_value"] == "≤ 6 months"
    assert comp["criteria"][1]["required_value"] == "≤ €50,000"


def test_comparison_row_fields(client, demo):
    rows = {r["vendor_name"]: r for r in get(client, f"/api/projects/{demo['project_id']}/comparison")["rows"]}
    h, k, q = rows[HARBORLINE], rows[KESTREL], rows[QUILLSTONE]

    assert (h["compatibility_label"], h["status"], h["hard_requirements"], h["hard_requirements_failed"]) == (
        "Strong compatibility", "warning", "100%", 0)
    assert (h["budget"], h["budget_status"], h["budget_summary"]) == ("€54.5K", "warning", "€4,500 over budget")
    assert (h["duration"], h["duration_status"], h["technology"], h["technology_status"]) == ("5 mo", "pass", "100%", "pass")
    assert (h["semantic_status"], h["semantic_summary"], h["semantic_score"]) == ("pass", "2 strong of 2", 1.0)
    assert h["major_concerns"] == ["Budget: €4,500 over budget"]

    assert (k["compatibility_label"], k["status"], k["hard_requirements"]) == ("Hard requirement failed", "fail", "Failed (1)")
    assert (k["hard_requirements_passed"], k["hard_requirements_failed"], k["hard_requirements_total"]) == (2, 1, 3)
    assert k["failed_hard_requirements"] == ["Duration"]
    assert (k["duration"], k["duration_status"], k["duration_summary"]) == ("8 mo", "fail", "2 months over the strict deadline")
    assert k["major_concerns"][0] == "Duration: 2 months over the strict deadline (hard requirement)"

    assert (q["compatibility_label"], q["status"], q["hard_requirements"]) == ("Mostly compatible with some concerns", "warning", "100%")
    assert (q["technology"], q["technology_status"], q["missing_technologies"]) == ("67%", "warning", ["PostgreSQL"])
    assert q["major_concerns"] == ["PostgreSQL: Not listed by vendor", "Company experience: 1 year below the minimum"]

    for row in rows.values():
        assert set(row["cells"]) == {"duration", "budget", "react-native", "node-js", "postgresql",
                                     "e-commerce-experience", "payment-integration", "company-experience"}
    assert rows[KESTREL]["cells"]["duration"] == {
        "status": "fail", "score": 0.0, "contribution": 0.0, "vendor_value": "8 months", "summary": "2 months over the strict deadline",
    }


def test_comparison_summaries_are_neutral(client, demo):
    comp = get(client, f"/api/projects/{demo['project_id']}/comparison")
    analysis = get(client, f"/api/projects/{demo['project_id']}/analysis")
    assert comp["ordering_note"].endswith("This order is a sorting aid, not a decision.")
    texts = []
    for r in comp["rows"]:
        texts += [r["summary"], r["compatibility_label"], r["status_label"], *r["major_concerns"]]
    for v in analysis["vendors"]:
        texts += [v["summary"], v["score_explanation"]]
    for text in texts:
        assert not any(word in text.lower() for word in FORBIDDEN), text
    labels = {r["compatibility_label"] for r in comp["rows"]}
    assert labels <= {"Strong compatibility", "Mostly compatible with some concerns", "Requires review", "Hard requirement failed"}


# --- repeated loading and isolation ---------------------------------------------------------

def test_repeated_loading_creates_independent_identical_copies(client):
    first, second = client.post("/api/demo").json(), client.post("/api/demo").json()
    assert first["project_id"] != second["project_id"]
    assert set(first["vendor_ids"]).isdisjoint(second["vendor_ids"])
    rows = lambda pid: [(r["vendor_name"], r["overall_score"]) for r in get(client, f"/api/projects/{pid}/comparison")["rows"]]  # noqa: E731
    assert rows(first["project_id"]) == rows(second["project_id"])


def test_editing_one_demo_copy_does_not_affect_another(client):
    first, second = client.post("/api/demo").json(), client.post("/api/demo").json()
    kestrel_first = first["vendor_ids"][1]
    vendor = get(client, f"/api/vendors/{kestrel_first}")
    payload = {k: vendor[k] for k in vendor_payload()} | {"proposed_duration": 6}
    assert client.put(f"/api/vendors/{kestrel_first}", json=payload).status_code == 200
    client.delete(f"/api/vendors/{first['vendor_ids'][2]}")

    first_rows = {r["vendor_name"]: r for r in get(client, f"/api/projects/{first['project_id']}/comparison")["rows"]}
    second_rows = {r["vendor_name"]: r for r in get(client, f"/api/projects/{second['project_id']}/comparison")["rows"]}
    assert first_rows[KESTREL]["hard_requirements_failed"] == 0 and QUILLSTONE not in first_rows
    assert second_rows[KESTREL]["hard_requirements_failed"] == 1 and QUILLSTONE in second_rows


def test_demo_loading_does_not_mutate_user_projects(make_client):
    client = make_client(ConstantSimilarityEmbedder(0.9), max_demo_projects=1)
    project = client.post("/api/projects", json=spec_project_payload()).json()
    client.post(f"/api/projects/{project['id']}/vendors", json=vendor_payload())
    snapshot = lambda: (  # noqa: E731
        get(client, f"/api/projects/{project['id']}"),
        get(client, f"/api/projects/{project['id']}/vendors"),
        [(r["vendor_id"], r["overall_score"], r["summary"]) for r in get(client, f"/api/projects/{project['id']}/comparison")["rows"]],
    )
    before = snapshot()
    for _ in range(3):  # also triggers pruning of older demo copies
        client.post("/api/demo")
    assert snapshot() == before
    demo_ids = [p["id"] for p in get(client, "/api/projects") if p["is_demo"]]
    assert len(demo_ids) == 1
