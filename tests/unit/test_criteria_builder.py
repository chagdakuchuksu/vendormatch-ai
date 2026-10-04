import pytest
from pydantic import ValidationError

from app.errors import InvalidCriteriaError, InvalidWeightsError
from app.schemas.criterion import CriterionIn
from app.schemas.enums import CriterionKind, CriterionSource, Flexibility, Importance, RequirementType, WeightSource
from app.services.criteria_builder import build_criteria
from tests.helpers import project, spec_example_project


def by_name(criteria):
    return {c.name: c for c in criteria}


# --- auto-generated criteria ----------------------------------------------------------------

def test_auto_technology_criteria_are_critical_and_hard():
    crits = build_criteria(project(required_technologies=["Node.js", "PostgreSQL"]))
    assert len(crits) == 2
    for c in crits:
        assert c.kind == CriterionKind.TECHNOLOGY
        assert c.source == CriterionSource.AUTO
        assert c.importance == Importance.CRITICAL
        assert c.requirement_type == RequirementType.HARD
        assert c.weight_source == WeightSource.IMPORTANCE_DEFAULT
        assert c.effective_weight == 4.0


def test_auto_budget_and_duration_defaults():
    crits = by_name(build_criteria(project(budget=50_000, max_duration=6)))
    budget, duration = crits["Budget"], crits["Duration"]
    assert (budget.importance, budget.requirement_type, budget.flexibility) == (
        Importance.HIGH, RequirementType.SOFT, Flexibility.FLEXIBLE,
    )
    assert (duration.importance, duration.requirement_type, duration.flexibility) == (
        Importance.HIGH, RequirementType.HARD, Flexibility.STRICT,
    )
    assert budget.source == duration.source == CriterionSource.AUTO


def test_user_technology_criterion_replaces_auto_one():
    """Auto criteria remain editable: a user criterion for the same technology wins."""
    p = project(
        required_technologies=["Node.js"],
        criteria=[CriterionIn(name="Node", kind="technology", technology="node", importance="low", requirement_type="soft")],
    )
    crits = build_criteria(p)
    assert len(crits) == 1
    assert crits[0].source == CriterionSource.USER
    assert crits[0].requirement_type == RequirementType.SOFT


def test_user_budget_criterion_replaces_auto_one():
    p = project(budget=10, criteria=[CriterionIn(name="Cost", kind="budget", flexibility="strict", requirement_type="hard")])
    crits = build_criteria(p)
    assert [c.name for c in crits] == ["Cost"]


def test_spec_example_materialization():
    crits = by_name(build_criteria(spec_example_project()))
    assert set(crits) == {"Duration", "Budget", "React Native", "E-commerce experience", "Company experience", "Node.js", "PostgreSQL"}
    assert sum(c.effective_weight for c in crits.values()) == 24
    assert crits["Duration"].normalized_weight == pytest.approx(4 / 24)
    assert sum(c.normalized_weight for c in crits.values()) == pytest.approx(1.0)


# --- importance vs. weight ------------------------------------------------------------------

def test_importance_only_sets_default_weight():
    p = project(criteria=[
        CriterionIn(name="A", kind="text", description="a", importance="critical"),
        CriterionIn(name="B", kind="text", description="b", importance="low"),
    ])
    a, b = build_criteria(p)
    assert a.normalized_weight == pytest.approx(4 / 5)
    assert b.normalized_weight == pytest.approx(1 / 5)


def test_explicit_weight_overrides_importance():
    p = project(criteria=[
        CriterionIn(name="A", kind="text", description="a", importance="critical", weight=1),
        CriterionIn(name="B", kind="text", description="b", importance="low", weight=1),
    ])
    a, b = build_criteria(p)
    assert a.normalized_weight == b.normalized_weight == pytest.approx(0.5)
    assert a.weight_source == WeightSource.EXPLICIT


def test_zero_weight_criterion_kept():
    p = project(criteria=[
        CriterionIn(name="A", kind="text", description="a", weight=0),
        CriterionIn(name="B", kind="text", description="b", weight=3),
    ])
    a, b = build_criteria(p)
    assert (a.normalized_weight, b.normalized_weight) == (0.0, 1.0)


def test_all_zero_weights_rejected():
    p = project(criteria=[CriterionIn(name="A", kind="text", description="a", weight=0)])
    with pytest.raises(InvalidWeightsError):
        build_criteria(p)


def test_negative_weight_rejected_by_schema():
    with pytest.raises(ValidationError):
        CriterionIn(name="A", kind="text", description="a", weight=-1)


# --- validation -----------------------------------------------------------------------------

def test_no_criteria_rejected():
    with pytest.raises(InvalidCriteriaError):
        build_criteria(project())


def test_budget_criterion_requires_project_budget():
    p = project(criteria=[CriterionIn(name="Budget", kind="budget", flexibility="flexible")])
    with pytest.raises(InvalidCriteriaError, match="budget"):
        build_criteria(p)


def test_duration_criterion_requires_project_duration():
    p = project(criteria=[CriterionIn(name="Duration", kind="duration", flexibility="strict")])
    with pytest.raises(InvalidCriteriaError, match="max_duration"):
        build_criteria(p)


def test_duplicate_budget_criteria_rejected():
    c = CriterionIn(name="Budget", kind="budget", flexibility="flexible")
    with pytest.raises(InvalidCriteriaError, match="Only one"):
        build_criteria(project(budget=1, criteria=[c, c]))


def test_duplicate_technology_criteria_rejected():
    p = project(criteria=[
        CriterionIn(name="PG", kind="technology", technology="PostgreSQL"),
        CriterionIn(name="Postgres", kind="technology", technology="postgres"),
    ])
    with pytest.raises(InvalidCriteriaError, match="more than one"):
        build_criteria(p)


def test_duplicate_required_technologies_rejected():
    with pytest.raises(InvalidCriteriaError):
        build_criteria(project(required_technologies=["Node.js", "node"]))


def test_unique_ids_for_same_names():
    p = project(criteria=[
        CriterionIn(name="Experience", kind="text", description="a"),
        CriterionIn(name="Experience", kind="text", description="b"),
    ])
    assert [c.id for c in build_criteria(p)] == ["experience", "experience-2"]


@pytest.mark.parametrize(
    "fields",
    [
        {"kind": "budget"},  # missing flexibility
        {"kind": "technology", "technology": "Go", "flexibility": "strict"},  # flexibility on non-numeric
        {"kind": "budget", "flexibility": "strict", "tolerance": 0.2},  # tolerance on strict
        {"kind": "experience", "flexibility": "flexible"},  # missing min_value
        {"kind": "technology"},  # missing technology
        {"kind": "text"},  # missing description
        {"kind": "text", "description": "x", "min_value": 3},  # min_value on wrong kind
        {"kind": "budget", "flexibility": "flexible", "tolerance": 1.5},  # tolerance out of range
    ],
)
def test_invalid_criterion_fields(fields):
    with pytest.raises(ValidationError):
        CriterionIn(name="X", **fields)


def test_blank_required_technology_rejected():
    with pytest.raises(ValidationError):
        project(required_technologies=["  "])
