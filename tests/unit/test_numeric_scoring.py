import pytest

from app.config import DEFAULT_SCORING_CONFIG as CFG
from app.schemas.enums import CriterionKind, CriterionStatus, Flexibility
from app.services.scoring.numeric import score_budget, score_deviation, score_duration, score_experience
from tests.helpers import criterion, project, vendor

BUDGET = CriterionKind.BUDGET
DURATION = CriterionKind.DURATION
EXPERIENCE = CriterionKind.EXPERIENCE


# --- the core curve -------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("d", "expected"),
    [(0.05, 0.96), (0.10, 0.84), (0.15, 0.64), (0.20, 0.36), (0.25, 0.0), (0.40, 0.0)],
)
def test_flexible_quadratic_curve_documented_values(d, expected):
    score, _ = score_deviation(d, Flexibility.FLEXIBLE, 0.25)
    assert score == pytest.approx(expected)


def test_flexible_penalty_grows_progressively():
    scores = [score_deviation(d, Flexibility.FLEXIBLE, 0.25)[0] for d in (0.05, 0.10, 0.15, 0.20)]
    losses = [1 - s for s in scores]
    increments = [b - a for a, b in zip(losses, losses[1:])]
    assert all(b > a for a, b in zip(increments, increments[1:]))


def test_flexible_statuses():
    assert score_deviation(0, Flexibility.FLEXIBLE, 0.25)[1] == CriterionStatus.PASS
    assert score_deviation(0.1, Flexibility.FLEXIBLE, 0.25)[1] == CriterionStatus.WARNING
    assert score_deviation(0.25, Flexibility.FLEXIBLE, 0.25)[1] == CriterionStatus.FAIL


def test_strict_any_deviation_fails():
    assert score_deviation(0.001, Flexibility.STRICT, 0.25) == (0.0, CriterionStatus.FAIL)
    assert score_deviation(0, Flexibility.STRICT, 0.25) == (1.0, CriterionStatus.PASS)


def test_negative_deviation_rejected():
    with pytest.raises(ValueError):
        score_deviation(-0.1, Flexibility.FLEXIBLE, 0.25)


# --- budget ---------------------------------------------------------------------------------

def test_budget_within_limit_passes_without_bonus():
    c = criterion(BUDGET, flexibility="flexible")
    r = score_budget(c, project(budget=50_000), vendor(proposed_budget=40_000), CFG)
    assert r.score == 1.0
    assert r.status == CriterionStatus.PASS
    assert r.deviation.direction == "under"
    assert r.summary == "€10,000 under budget"


def test_budget_exactly_at_limit_passes():
    c = criterion(BUDGET, flexibility="strict")
    r = score_budget(c, project(budget=50_000), vendor(proposed_budget=50_000), CFG)
    assert (r.score, r.status, r.deviation.direction) == (1.0, CriterionStatus.PASS, "none")


def test_flexible_budget_deviation_is_partial_penalty_not_failure():
    c = criterion(BUDGET, flexibility="flexible", requirement_type="soft", importance="high")
    r = score_budget(c, project(budget=50_000, currency="EUR"), vendor(proposed_budget=55_000), CFG)
    assert r.score == pytest.approx(0.84)
    assert r.status == CriterionStatus.WARNING
    assert not r.hard_failure
    assert r.deviation.absolute == pytest.approx(5_000)
    assert r.deviation.relative == pytest.approx(0.10)
    assert r.summary == "€5,000 over budget"
    assert "€5,000 (10%) above the preferred maximum budget of €50,000" in r.explanation
    assert "Soft + Flexible" in r.explanation


def test_vendor_exceeding_strict_budget_fails():
    c = criterion(BUDGET, flexibility="strict", requirement_type="soft")
    r = score_budget(c, project(budget=50_000), vendor(proposed_budget=50_001), CFG)
    assert (r.score, r.status, r.hard_failure) == (0.0, CriterionStatus.FAIL, False)


def test_flexible_budget_beyond_tolerance_fails():
    c = criterion(BUDGET, flexibility="flexible")
    r = score_budget(c, project(budget=50_000), vendor(proposed_budget=65_000), CFG)
    assert (r.score, r.status) == (0.0, CriterionStatus.FAIL)
    assert "exceeds the 25% tolerance" in r.explanation


def test_custom_tolerance_per_criterion():
    c = criterion(BUDGET, flexibility="flexible", tolerance=0.5)
    r = score_budget(c, project(budget=100), vendor(proposed_budget=125), CFG)
    assert r.score == pytest.approx(1 - (0.25 / 0.5) ** 2)  # 0.75


def test_hard_flexible_within_tolerance_is_not_hard_failure():
    c = criterion(BUDGET, flexibility="flexible", requirement_type="hard")
    r = score_budget(c, project(budget=100), vendor(proposed_budget=110), CFG)
    assert r.status == CriterionStatus.WARNING
    assert not r.hard_failure


def test_hard_flexible_beyond_tolerance_is_hard_failure():
    c = criterion(BUDGET, flexibility="flexible", requirement_type="hard", importance="high")
    r = score_budget(c, project(budget=100), vendor(proposed_budget=130), CFG)
    assert r.hard_failure
    assert r.penalty_factor == 0.6


@pytest.mark.parametrize("requirement_type", ["hard", "soft"])
def test_missing_vendor_budget(requirement_type):
    c = criterion(BUDGET, flexibility="flexible", requirement_type=requirement_type)
    r = score_budget(c, project(budget=50_000), vendor(proposed_budget=None), CFG)
    assert (r.score, r.status) == (0.0, CriterionStatus.MISSING)
    assert r.vendor_value == "not stated"
    assert r.hard_failure is (requirement_type == "hard")
    assert "cannot be verified" in r.explanation


def test_budget_requires_project_budget():
    with pytest.raises(ValueError):
        score_budget(criterion(BUDGET), project(budget=None), vendor(proposed_budget=1), CFG)


def test_non_euro_currency_formatting():
    r = score_budget(criterion(BUDGET), project(budget=1000, currency="CHF"), vendor(proposed_budget=900), CFG)
    assert r.required_value == "≤ 1,000 CHF"


# --- duration -------------------------------------------------------------------------------

def test_strict_duration_violation_is_hard_failure():
    c = criterion(DURATION, flexibility="strict", requirement_type="hard", importance="critical")
    r = score_duration(c, project(max_duration=6), vendor(proposed_duration=8), CFG)
    assert (r.score, r.status) == (0.0, CriterionStatus.FAIL)
    assert r.hard_failure and r.penalty_factor == 0.5
    assert r.summary == "2 months over the strict deadline"
    assert "8 months is 2 months (33.3%) above the strict maximum duration of 6 months" in r.explanation
    assert "failed hard requirement" in r.explanation


def test_duration_within_limit_passes():
    c = criterion(DURATION, flexibility="strict", requirement_type="hard")
    r = score_duration(c, project(max_duration=6), vendor(proposed_duration=5), CFG)
    assert (r.score, r.status, r.hard_failure) == (1.0, CriterionStatus.PASS, False)
    assert r.summary == "1 month ahead of the maximum duration"


def test_flexible_duration_deviation():
    c = criterion(DURATION, flexibility="flexible")
    r = score_duration(c, project(max_duration=10), vendor(proposed_duration=11), CFG)
    assert r.score == pytest.approx(0.84)


def test_duration_unit_conversion_months_to_weeks():
    c = criterion(DURATION, flexibility="strict")
    r = score_duration(c, project(max_duration=20, duration_unit="weeks"), vendor(proposed_duration=6), CFG)
    assert r.status == CriterionStatus.FAIL  # 6 months = 26 weeks > 20 weeks
    assert r.deviation.absolute == 6


def test_missing_vendor_duration_hard():
    c = criterion(DURATION, flexibility="strict", requirement_type="hard")
    r = score_duration(c, project(max_duration=6), vendor(), CFG)
    assert r.status == CriterionStatus.MISSING
    assert r.hard_failure


# --- experience (lower bound) ---------------------------------------------------------------

def test_experience_above_minimum_passes():
    c = criterion(EXPERIENCE, flexibility="flexible", min_value=5)
    r = score_experience(c, vendor(years_experience=8), CFG)
    assert (r.score, r.status) == (1.0, CriterionStatus.PASS)
    assert r.summary == "3 years above the minimum"


def test_experience_shortfall_flexible():
    c = criterion(EXPERIENCE, flexibility="flexible", min_value=5)
    r = score_experience(c, vendor(years_experience=4), CFG)  # d = 0.2
    assert r.score == pytest.approx(0.36)
    assert r.status == CriterionStatus.WARNING
    assert r.summary == "1 year below the minimum"


def test_experience_shortfall_strict():
    c = criterion(EXPERIENCE, flexibility="strict", min_value=5)
    r = score_experience(c, vendor(years_experience=4.5), CFG)
    assert (r.score, r.status) == (0.0, CriterionStatus.FAIL)


def test_experience_missing():
    c = criterion(EXPERIENCE, flexibility="flexible", min_value=5)
    assert score_experience(c, vendor(), CFG).status == CriterionStatus.MISSING


def test_scorer_rejects_wrong_kind():
    with pytest.raises(ValueError):
        score_experience(criterion(BUDGET), vendor(), CFG)
