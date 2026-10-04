import pytest

from app.config import DEFAULT_SCORING_CONFIG as CFG
from app.schemas.enums import CriterionKind, CriterionStatus
from app.services.scoring.aggregate import aggregate
from app.services.scoring.common import make_result
from tests.helpers import criterion

TEXT = CriterionKind.TEXT


def result(weight, score, status, *, requirement_type="soft", importance="medium", name="C"):
    c = criterion(TEXT, name=name, description="d", normalized_weight=weight, requirement_type=requirement_type, importance=importance)
    return make_result(c, CFG, score=score, status=status, required_value="r", vendor_value="v", summary="s", explanation="e")


PASS, WARN, FAIL, MISSING = (CriterionStatus.PASS, CriterionStatus.WARNING, CriterionStatus.FAIL, CriterionStatus.MISSING)


def test_all_requirements_satisfied_scores_100():
    agg = aggregate([result(0.5, 1, PASS, requirement_type="hard"), result(0.5, 1, PASS)])
    assert (agg.base_score, agg.penalty_factor, agg.overall_score) == (100, 1, 100)


def test_weighted_sum():
    agg = aggregate([result(0.75, 1, PASS), result(0.25, 0.4, WARN)])
    assert agg.overall_score == pytest.approx(85.0)


def test_soft_failure_only_loses_its_points():
    agg = aggregate([result(0.8, 1, PASS), result(0.2, 0, FAIL)])
    assert agg.penalty_factor == 1
    assert agg.overall_score == pytest.approx(80.0)


@pytest.mark.parametrize(("importance", "factor"), [("critical", 0.5), ("high", 0.6), ("medium", 0.7), ("low", 0.8)])
def test_hard_failure_scores_zero_and_applies_multiplier(importance, factor):
    agg = aggregate([result(0.8, 1, PASS), result(0.2, 0, FAIL, requirement_type="hard", importance=importance)])
    assert agg.base_score == pytest.approx(80.0)
    assert agg.penalty_factor == factor
    assert agg.overall_score == pytest.approx(80.0 * factor)


def test_hard_failure_hurts_more_than_equivalent_soft_failure():
    soft = aggregate([result(0.8, 1, PASS), result(0.2, 0, FAIL, requirement_type="soft")])
    hard = aggregate([result(0.8, 1, PASS), result(0.2, 0, FAIL, requirement_type="hard")])
    assert hard.overall_score < soft.overall_score


def test_multiple_hard_failures_compound():
    agg = aggregate([
        result(0.5, 1, PASS),
        result(0.25, 0, FAIL, requirement_type="hard", importance="critical"),
        result(0.25, 0, MISSING, requirement_type="hard", importance="high"),
    ])
    assert agg.penalty_factor == pytest.approx(0.5 * 0.6)
    assert agg.overall_score == pytest.approx(50 * 0.3)


def test_zero_weight_hard_failure_still_penalizes():
    agg = aggregate([result(1.0, 1, PASS), result(0.0, 0, FAIL, requirement_type="hard", importance="critical")])
    assert agg.base_score == pytest.approx(100.0)
    assert agg.overall_score == pytest.approx(50.0)


def test_importance_does_not_change_points_for_equal_weights():
    """No double counting: with equal weights, a soft failure costs the same whatever its importance."""
    crit_loss = aggregate([result(0.5, 1, PASS), result(0.5, 0, FAIL, importance="critical")])
    low_loss = aggregate([result(0.5, 1, PASS), result(0.5, 0, FAIL, importance="low")])
    assert crit_loss.overall_score == low_loss.overall_score == pytest.approx(50.0)


def test_counts_by_type_and_status():
    agg = aggregate([
        result(0.2, 1, PASS, requirement_type="hard"),
        result(0.2, 0.5, WARN, requirement_type="hard"),
        result(0.2, 0, MISSING, requirement_type="hard"),
        result(0.2, 1, PASS),
        result(0.2, 0, FAIL),
    ])
    c = agg.counts
    assert (c.hard_passed, c.hard_warning, c.hard_failed) == (1, 1, 1)
    assert (c.soft_passed, c.soft_warning, c.soft_failed) == (1, 0, 1)
