import pytest

from app.errors import SemanticModelUnavailableError
from tests.api.conftest import TECHS, spec_project_payload, vendor_payload
from tests.fakes import ConstantSimilarityEmbedder

VENDOR_A = vendor_payload(name="Vendor A", proposed_budget=55000, proposed_duration=5, years_experience=8)
VENDOR_B = vendor_payload(name="Vendor B", proposed_budget=40000, proposed_duration=8, years_experience=10)


@pytest.fixture
def strong_client(make_client):
    """Semantic matches always strong, so scores equal the M1 golden values."""
    return make_client(ConstantSimilarityEmbedder(0.9))


def setup(client, *vendors, **project_overrides):
    project = client.post("/api/projects", json=spec_project_payload(**project_overrides)).json()
    ids = [client.post(f"/api/projects/{project['id']}/vendors", json=v).json()["id"] for v in vendors]
    return project["id"], ids


def vendor_result(analysis, name):
    return next(v for v in analysis["vendors"] if v["vendor_name"] == name)


def criterion_result(vendor, name):
    return next(c for c in vendor["criteria"] if c["name"] == name)


# --- analysis -------------------------------------------------------------------------------

def test_spec_golden_scores_through_api(strong_client):
    pid, _ = setup(strong_client, VENDOR_B, VENDOR_A)
    a = strong_client.get(f"/api/projects/{pid}/analysis").json()
    assert a["vendor_count"] == 2 and a["scoring_version"] == "1.2"
    assert "Decision support only" in a["disclaimer"]
    assert [v["vendor_name"] for v in a["vendors"]] == ["Vendor A", "Vendor B"]  # ordered by score
    assert vendor_result(a, "Vendor A")["overall_score"] == 98.0
    assert vendor_result(a, "Vendor B")["overall_score"] == 41.7


def test_hard_requirement_failure_is_explained_not_hidden(strong_client):
    pid, _ = setup(strong_client, VENDOR_A, VENDOR_B)
    b = vendor_result(strong_client.get(f"/api/projects/{pid}/analysis").json(), "Vendor B")
    assert b["hard_requirements_met"] is False
    assert b["status_label"] == "Hard requirement failed: Duration"
    assert (b["base_score"], b["hard_penalty_factor"]) == (83.3, 0.5)
    d = criterion_result(b, "Duration")
    assert (d["status"], d["score"], d["hard_failure"], d["penalty_factor"]) == ("fail", 0.0, True, 0.5)
    assert d["required_value"] == "≤ 6 months" and d["vendor_value"] == "8 months"
    assert d["deviation"] == {"absolute": 2.0, "relative": pytest.approx(1 / 3), "unit": "months", "direction": "over"}
    assert "failed hard requirement" in d["explanation"]
    assert len(b["criteria"]) == 7


def test_multiple_hard_failures(strong_client):
    v = vendor_payload(name="C", proposed_duration=9, technologies=["Flutter", "Node.js", "PostgreSQL"])
    pid, _ = setup(strong_client, v)
    c = strong_client.get(f"/api/projects/{pid}/analysis").json()["vendors"][0]
    assert c["counts"]["hard_failed"] == 2
    assert c["hard_penalty_factor"] == 0.25


def test_semantic_criterion_evidence_through_api(client):
    v = vendor_payload(proposal_text="Our office has plants. We built online e-commerce shops for retail brands.")
    pid, _ = setup(client, v)
    vendor = client.get(f"/api/projects/{pid}/analysis").json()["vendors"][0]
    sem = criterion_result(vendor, "E-commerce experience")
    ev = sem["evidence"]
    assert ev["requirement_text"] == "Previous e-commerce experience"
    assert ev["matched_text"] == "We built online e-commerce shops for retail brands."
    assert ev["source"] == "proposal"
    assert set(ev) >= {"similarity", "normalized_score", "strength", "lower_threshold", "upper_threshold"}
    assert sem["status"] in ("pass", "warning", "fail") and sem["summary"] and sem["explanation"]


def test_semantic_results_do_not_change_structured_criteria(make_client):
    results = []
    for sim in (0.0, 0.45, 0.9):
        c = make_client(ConstantSimilarityEmbedder(sim))
        pid, _ = setup(c, VENDOR_B)
        vendor = c.get(f"/api/projects/{pid}/analysis").json()["vendors"][0]
        results.append([cr for cr in vendor["criteria"] if cr["kind"] != "text"])
        assert vendor["hard_requirements_met"] is False  # semantic can't rescue the hard failure
        c.delete(f"/api/projects/{pid}")
    assert results[0] == results[1] == results[2]


def test_analysis_without_vendors(client, project):
    a = client.get(f"/api/projects/{project['id']}/analysis").json()
    assert (a["vendor_count"], a["vendors"]) == (0, [])


def test_analysis_reflects_current_data(strong_client):
    pid, (a_id, b_id) = setup(strong_client, VENDOR_A, VENDOR_B)
    before = strong_client.get(f"/api/projects/{pid}/analysis").json()
    assert vendor_result(before, "Vendor B")["overall_score"] == 41.7

    # Vendor B revises its timeline -> hard failure disappears.
    strong_client.put(f"/api/vendors/{b_id}", json={**VENDOR_B, "proposed_duration": 6})
    after = strong_client.get(f"/api/projects/{pid}/analysis").json()
    assert vendor_result(after, "Vendor B")["hard_requirements_met"] is True
    assert vendor_result(after, "Vendor B")["overall_score"] == 100.0

    # The project relaxes its budget -> Vendor A no longer over budget.
    strong_client.put(f"/api/projects/{pid}", json=spec_project_payload(budget=60000))
    latest = strong_client.get(f"/api/projects/{pid}/analysis").json()
    assert vendor_result(latest, "Vendor A")["overall_score"] == 100.0

    # A deleted vendor disappears from the analysis.
    strong_client.delete(f"/api/vendors/{a_id}")
    assert [v["vendor_name"] for v in strong_client.get(f"/api/projects/{pid}/analysis").json()["vendors"]] == ["Vendor B"]


def test_semantic_model_unavailable_returns_503(make_client):
    class BrokenEmbedder:
        def encode(self, texts):
            raise SemanticModelUnavailableError("The local semantic model could not be loaded.")

    c = make_client(BrokenEmbedder())
    pid, _ = setup(c, VENDOR_A)
    r = c.get(f"/api/projects/{pid}/analysis")
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "semantic_model_unavailable"


def test_project_without_text_criteria_never_calls_embedder(make_client):
    class ExplodingEmbedder:
        def encode(self, texts):
            raise AssertionError("embedder must not be used")

    c = make_client(ExplodingEmbedder())
    payload = spec_project_payload(criteria=[])
    pid, _ = setup(c, VENDOR_A, **{k: v for k, v in payload.items() if k != "name"})
    assert c.get(f"/api/projects/{pid}/analysis").status_code == 200


# --- comparison -----------------------------------------------------------------------------

def test_comparison_rows(strong_client):
    c_vendor = vendor_payload(name="Vendor C", proposed_budget=31000, proposed_duration=26, duration_unit="weeks",
                              technologies=["React Native", "Node.js", "MySQL"])
    pid, ids = setup(strong_client, VENDOR_A, VENDOR_B, c_vendor)
    comp = strong_client.get(f"/api/projects/{pid}/comparison").json()
    rows = {r["vendor_name"]: r for r in comp["rows"]}
    # B (duration) and C (PostgreSQL, auto Critical + Hard) both fail one hard requirement and tie
    # at 41.7; ties are ordered by name.
    assert [(r["vendor_name"], r["overall_score"]) for r in comp["rows"]] == [
        ("Vendor A", 98.0), ("Vendor B", 41.7), ("Vendor C", 41.7),
    ]
    assert "Decision support only" in comp["disclaimer"]

    a = rows["Vendor A"]
    assert (a["overall_score"], a["status"], a["hard_requirements"]) == (98.0, "warning", "100%")
    assert (a["budget"], a["budget_value"], a["budget_status"]) == ("€55K", 55000, "warning")
    assert (a["duration"], a["duration_status"], a["technology"]) == ("5 mo", "pass", "100%")

    b = rows["Vendor B"]
    assert (b["status"], b["hard_requirements"], b["hard_requirements_passed"], b["hard_requirements_total"]) == ("fail", "Failed (1)", 3, 4)
    assert (b["budget"], b["duration"], b["duration_status"]) == ("€40K", "8 mo", "fail")

    c = rows["Vendor C"]
    assert (c["duration"], c["duration_status"]) == ("26 wk", "pass")  # 26 weeks = 182 days = 6 months exactly
    assert (c["technology"], c["technology_coverage"]) == ("67%", pytest.approx(2 / 3))
    assert c["status"] == "fail"  # PostgreSQL is an auto Critical + Hard requirement


def test_comparison_matches_analysis_order_and_scores(client):
    pid, _ = setup(client, VENDOR_A, VENDOR_B, vendor_payload(name="Vendor C", technologies=TECHS, proposed_budget=45000))
    analysis = client.get(f"/api/projects/{pid}/analysis").json()
    comparison = client.get(f"/api/projects/{pid}/comparison").json()
    assert [(v["vendor_id"], v["overall_score"]) for v in analysis["vendors"]] == [
        (r["vendor_id"], r["overall_score"]) for r in comparison["rows"]
    ]


def test_six_month_vendor_meets_strict_26_week_deadline(strong_client):
    """Regression (Northgale): 6 months vs a strict 26-week deadline is equal, not 0.07 weeks over."""
    payload = spec_project_payload(max_duration=26, duration_unit="weeks")
    pid, _ = setup(strong_client, vendor_payload(name="Northgale", proposed_duration=6, duration_unit="months"),
                   **{k: v for k, v in payload.items() if k != "name"})
    vendor = strong_client.get(f"/api/projects/{pid}/analysis").json()["vendors"][0]
    d = criterion_result(vendor, "Duration")
    assert (d["status"], d["score"], d["hard_failure"]) == ("pass", 1.0, False)
    assert d["vendor_value"] == "6 months (≈ 26 weeks)"
    assert vendor["hard_requirements_met"] is True
