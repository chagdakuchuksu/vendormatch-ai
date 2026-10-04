"""End-to-end scoring of single vendors with materialized criteria (no DB, no model)."""

import pytest

from app.errors import ScoringError
from app.schemas.criterion import CriterionIn
from app.schemas.enums import CriterionKind, CriterionStatus
from app.services.criteria_builder import build_criteria
from app.services.scoring.engine import evaluate_vendor
from tests.helpers import FixedSemanticScorer, criterion, project, spec_example_project, vendor

TECHS = ["React Native", "Node.js", "PostgreSQL"]


@pytest.fixture
def spec():
    p = spec_example_project()
    return p, build_criteria(p)


def evaluate(spec, v, semantic_score=1.0):
    p, crits = spec
    return evaluate_vendor(p, crits, v, semantic_scorer=FixedSemanticScorer(semantic_score))


# --- golden test: the spec example ----------------------------------------------------------

def test_spec_vendor_a_over_flexible_budget_stays_competitive(spec):
    a = evaluate(spec, vendor(name="Vendor A", proposed_budget=55_000, proposed_duration=5, years_experience=8, technologies=TECHS))
    # Budget weight 3/24, score 1 - (0.10/0.25)^2 = 0.84  ->  loses 3/24 * 0.16 * 100 = 2.0 points
    assert a.overall_score == 98.0
    assert a.hard_requirements_met
    assert a.hard_penalty_factor == 1.0
    budget = next(r for r in a.criteria if r.name == "Budget")
    assert budget.status == CriterionStatus.WARNING
    assert budget.summary == "€5,000 over budget"
    assert a.concerns == ["Budget: €5,000 over budget"]
    assert a.status_label == "All hard requirements met, with warnings"


def test_spec_vendor_b_strict_duration_violation(spec):
    b = evaluate(spec, vendor(name="Vendor B", proposed_budget=40_000, proposed_duration=8, years_experience=10, technologies=TECHS))
    # Duration weight 4/24 lost -> base 83.3; Critical hard failure -> x0.5
    assert b.base_score == 83.3
    assert b.hard_penalty_factor == 0.5
    assert b.overall_score == 41.7
    assert not b.hard_requirements_met
    assert b.status_label == "Hard requirement failed: Duration"
    assert b.missing_requirements == ["Duration"]
    duration = next(r for r in b.criteria if r.name == "Duration")
    assert duration.hard_failure and duration.score == 0
    assert duration.summary == "2 months over the strict deadline"
    assert b.duration_deviation.absolute == pytest.approx(2)


def test_spec_vendor_a_ranks_above_vendor_b(spec):
    a = evaluate(spec, vendor(name="A", proposed_budget=55_000, proposed_duration=5, years_experience=8, technologies=TECHS))
    b = evaluate(spec, vendor(name="B", proposed_budget=40_000, proposed_duration=8, years_experience=10, technologies=TECHS))
    assert a.overall_score > b.overall_score


def test_failed_vendor_is_reported_not_dropped(spec):
    b = evaluate(spec, vendor(name="B", proposed_budget=40_000, proposed_duration=8, years_experience=10, technologies=TECHS))
    assert len(b.criteria) == len(spec[1])
    assert b.overall_score > 0


# --- other vendor-level behaviour -----------------------------------------------------------

def test_all_requirements_satisfied(spec):
    v = evaluate(spec, vendor(proposed_budget=45_000, proposed_duration=6, years_experience=12, technologies=TECHS))
    assert v.overall_score == 100.0
    assert v.status_label == "All requirements met"
    assert v.missing_requirements == [] and v.concerns == []
    assert v.technology_coverage == 1.0


def test_multiple_hard_requirements_failed(spec):
    v = evaluate(spec, vendor(proposed_budget=45_000, proposed_duration=9, years_experience=12, technologies=["Flutter", "Node.js", "PostgreSQL"]))
    assert v.counts.hard_failed == 2
    assert v.hard_penalty_factor == 0.25
    # base = 100 - (4 + 4)/24 * 100 = 66.67 -> x0.25
    assert v.overall_score == pytest.approx(16.7)
    assert v.status_label == "Hard requirement failed: Duration, React Native"


def test_missing_budget_and_duration(spec):
    v = evaluate(spec, vendor(years_experience=6, technologies=TECHS))
    statuses = {r.name: r.status for r in v.criteria}
    assert statuses["Budget"] == statuses["Duration"] == CriterionStatus.MISSING
    assert not v.hard_requirements_met  # duration is a hard requirement
    assert {"Budget", "Duration"} <= set(v.missing_requirements)
    assert v.budget_deviation is None and v.duration_deviation is None


def test_soft_semantic_partial_lowers_score(spec):
    full = evaluate(spec, vendor(proposed_budget=45_000, proposed_duration=6, years_experience=12, technologies=TECHS), 1.0)
    partial = evaluate(spec, vendor(proposed_budget=45_000, proposed_duration=6, years_experience=12, technologies=TECHS), 0.5)
    assert partial.overall_score == pytest.approx(full.overall_score - 3 / 24 * 50, abs=0.05)


def test_technology_coverage(spec):
    v = evaluate(spec, vendor(proposed_budget=45_000, proposed_duration=6, years_experience=12, technologies=["React Native", "MySQL"]))
    assert v.technology_coverage == pytest.approx(1 / 3)


def test_low_bid_concern_has_no_score_effect():
    p = project(budget=100_000, criteria=[CriterionIn(name="Budget", kind="budget", flexibility="flexible")])
    crits = build_criteria(p)
    v = evaluate_vendor(p, crits, vendor(proposed_budget=50_000))
    assert v.overall_score == 100.0
    assert len(v.concerns) == 1 and "50% below the project budget" in v.concerns[0]


def test_text_criterion_without_semantic_scorer_raises(spec):
    p, crits = spec
    with pytest.raises(ScoringError, match="semantic scorer"):
        evaluate_vendor(p, crits, vendor())


def test_deterministic_numeric_only_project_needs_no_semantic_scorer():
    p = project(budget=50_000, max_duration=6, required_technologies=["Go"])
    v = evaluate_vendor(p, build_criteria(p), vendor(proposed_budget=50_000, proposed_duration=6, technologies=["golang"]))
    assert v.overall_score == 100.0


def test_unnormalized_criteria_rejected():
    crit = criterion(CriterionKind.TECHNOLOGY, technology="Go", normalized_weight=0.5)
    with pytest.raises(ScoringError, match="normalized"):
        evaluate_vendor(project(), [crit], vendor())


def test_results_are_deterministic(spec):
    v = vendor(proposed_budget=55_000, proposed_duration=5, years_experience=4, technologies=TECHS)
    assert evaluate(spec, v).model_dump() == evaluate(spec, v).model_dump()
