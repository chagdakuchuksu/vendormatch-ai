"""Linear penalty curve for flexible numeric criteria (used by the project form for deadline and experience)."""

import pytest
from pydantic import ValidationError

from app.config import DEFAULT_SCORING_CONFIG as CFG
from app.schemas.criterion import CriterionIn
from app.schemas.enums import CriterionKind, CriterionStatus, Flexibility, PenaltyCurve
from app.services.scoring.numeric import score_deviation, score_duration, score_experience
from tests.helpers import criterion, project, vendor

LINEAR, QUADRATIC = PenaltyCurve.LINEAR, PenaltyCurve.QUADRATIC


@pytest.mark.parametrize(("d", "expected"), [(0, 1.0), (1 / 12, 5 / 6), (2 / 12, 2 / 3), (0.25, 0.5), (4 / 12, 1 / 3), (0.5, 0.0), (0.9, 0.0)])
def test_linear_curve_values(d, expected):
    score, _ = score_deviation(d, Flexibility.FLEXIBLE, 0.5, LINEAR)
    assert score == pytest.approx(expected)


def test_linear_penalty_is_proportional():
    losses = [1 - score_deviation(d, Flexibility.FLEXIBLE, 0.5, LINEAR)[0] for d in (0.1, 0.2, 0.3, 0.4)]
    steps = [b - a for a, b in zip(losses, losses[1:])]
    assert steps == pytest.approx([0.2, 0.2, 0.2])


def test_default_curve_is_still_quadratic():
    assert score_deviation(0.1, Flexibility.FLEXIBLE, 0.25)[0] == pytest.approx(0.84)
    assert score_deviation(0.1, Flexibility.FLEXIBLE, 0.25, QUADRATIC)[0] == pytest.approx(0.84)


def deadline(months, target=12):
    c = criterion(CriterionKind.DURATION, flexibility="flexible", tolerance=0.5, curve="linear", requirement_type="soft", importance="critical")
    return score_duration(c, project(max_duration=target), vendor(proposed_duration=months), CFG)


def test_one_month_late_is_a_partial_penalty_not_zero():
    r = deadline(13)
    assert (r.status, r.hard_failure) == (CriterionStatus.WARNING, False)
    assert r.score == pytest.approx(5 / 6)
    assert r.summary == "1 month over the preferred duration"
    assert "in proportion to the deviation" in r.explanation


@pytest.mark.parametrize(("months", "score"), [(12, 1.0), (14, 2 / 3), (15, 0.5), (16, 1 / 3), (18, 0.0), (24, 0.0)])
def test_deadline_table(months, score):
    assert deadline(months).score == pytest.approx(score)


def test_points_lost_scale_with_weight():
    heavy = criterion(CriterionKind.DURATION, flexibility="flexible", tolerance=0.5, curve="linear", normalized_weight=0.6)
    light = criterion(CriterionKind.DURATION, flexibility="flexible", tolerance=0.5, curve="linear", normalized_weight=0.1)
    p, v = project(max_duration=12), vendor(proposed_duration=13)
    assert score_duration(heavy, p, v, CFG).points_lost == pytest.approx(60 / 6)
    assert score_duration(light, p, v, CFG).points_lost == pytest.approx(10 / 6)


@pytest.mark.parametrize(("years", "score"), [(4, 1.0), (3, 0.5), (2.5, 0.25), (2, 0.0)])
def test_experience_linear(years, score):
    c = criterion(CriterionKind.EXPERIENCE, flexibility="flexible", tolerance=0.5, curve="linear", min_value=4)
    assert score_experience(c, vendor(years_experience=years), CFG).score == pytest.approx(score)


def test_curve_rejected_on_strict_and_non_numeric_criteria():
    with pytest.raises(ValidationError):
        CriterionIn(name="D", kind="duration", flexibility="strict", curve="linear")
    with pytest.raises(ValidationError):
        CriterionIn(name="T", kind="technology", technology="Go", curve="linear")
