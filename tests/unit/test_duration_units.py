"""Duration normalization through days (1 week = 7 days, 1 month = 364/12 = 30 1/3 days)."""

from fractions import Fraction

import pytest

from app.config import DEFAULT_SCORING_CONFIG as CFG
from app.schemas.enums import CriterionKind, CriterionStatus, DurationUnit
from app.services.scoring.numeric import score_duration
from app.utils.units import DAYS_PER_UNIT, convert_duration, to_days
from tests.helpers import criterion, project, vendor

W, M = DurationUnit.WEEKS, DurationUnit.MONTHS


def duration(value, unit, *, target, target_unit, flexibility="strict", requirement_type="hard"):
    c = criterion(CriterionKind.DURATION, flexibility=flexibility, requirement_type=requirement_type, importance="critical")
    return score_duration(c, project(max_duration=target, duration_unit=target_unit), vendor(proposed_duration=value, duration_unit=unit), CFG)


# --- conversion table -----------------------------------------------------------------------

def test_conversion_constants():
    assert DAYS_PER_UNIT == {W: 7, M: Fraction(91, 3)}


@pytest.mark.parametrize(
    ("months", "days", "weeks"),
    [(1, Fraction(91, 3), Fraction(13, 3)), (3, 91, 13), (6, 182, 26), (9, 273, 39), (12, 364, 52)],
)
def test_months_to_days_and_weeks_are_exact(months, days, weeks):
    assert to_days(months, M) == days
    assert to_days(weeks, W) == days
    assert convert_duration(months, M, W) == float(weeks)
    assert convert_duration(float(weeks), W, M) == pytest.approx(months, abs=1e-12)


def test_whole_quarters_convert_without_floating_point_drift():
    assert convert_duration(6, M, W) == 26.0
    assert convert_duration(26, W, M) == 6.0


@pytest.mark.parametrize("value", [0.5, 5, 6, 6.07, 26, 1e6])
@pytest.mark.parametrize("unit", [W, M])
def test_same_unit_is_identity(value, unit):
    assert convert_duration(value, unit, unit) == value


# --- 6 months vs 26 weeks -------------------------------------------------------------------

@pytest.mark.parametrize(
    ("value", "unit", "target", "target_unit"),
    [(6, M, 26, W), (26, W, 6, M)],
)
def test_six_months_equals_twenty_six_weeks_under_strict_limit(value, unit, target, target_unit):
    r = duration(value, unit, target=target, target_unit=target_unit)
    assert (r.score, r.status, r.hard_failure) == (1.0, CriterionStatus.PASS, False)
    assert r.deviation.direction == "none" and r.deviation.absolute == 0
    assert r.summary == "Meets requirement exactly"


def test_six_months_vendor_value_shows_exact_conversion():
    r = duration(6, M, target=26, target_unit=W)
    assert r.vendor_value == "6 months (≈ 26 weeks)"
    assert r.required_value == "≤ 26 weeks"


# --- 3 months vs 12 weeks -------------------------------------------------------------------

def test_three_months_exceeds_strict_twelve_weeks_by_one_week():
    r = duration(3, M, target=12, target_unit=W)  # 91 days vs 84 days: a real difference
    assert (r.score, r.status, r.hard_failure) == (0.0, CriterionStatus.FAIL, True)
    assert r.deviation.absolute == pytest.approx(1.0)
    assert r.deviation.relative == pytest.approx(1 / 12)
    assert r.summary == "1 week over the strict deadline"


def test_twelve_weeks_within_three_months():
    r = duration(12, W, target=3, target_unit=M)
    assert r.status == CriterionStatus.PASS
    assert r.deviation.direction == "under"
    assert r.deviation.absolute == pytest.approx(3 / 13)  # 7 days = 3/13 of a month


def test_twelve_months_equals_fifty_two_weeks():
    assert duration(12, M, target=52, target_unit=W).status == CriterionStatus.PASS
    assert duration(52, W, target=12, target_unit=M).status == CriterionStatus.PASS


# --- same-unit comparisons (unchanged behaviour) --------------------------------------------

@pytest.mark.parametrize(("value", "unit"), [(26, W), (6, M)])
def test_same_unit_strict_equality_passes(value, unit):
    r = duration(value, unit, target=value, target_unit=unit)
    assert (r.score, r.status) == (1.0, CriterionStatus.PASS)


@pytest.mark.parametrize(
    ("value", "target", "unit", "absolute"),
    [(26.1, 26, W, 0.1), (6.01, 6, M, 0.01), (8, 6, M, 2)],
)
def test_same_unit_over_strict_limit_fails(value, target, unit, absolute):
    r = duration(value, unit, target=target, target_unit=unit)
    assert (r.score, r.status, r.hard_failure) == (0.0, CriterionStatus.FAIL, True)
    assert r.deviation.absolute == pytest.approx(absolute)


# --- slightly over the strict limit across units --------------------------------------------

@pytest.mark.parametrize(
    ("value", "unit", "target", "target_unit"),
    [
        (27, W, 6, M),  # 189 days vs 182 days
        (6.05, M, 26, W),  # 183.5 days vs 182 days
        (26.2, W, 6, M),  # 183.4 days vs 182 days
    ],
)
def test_slightly_over_strict_limit_across_units_fails(value, unit, target, target_unit):
    r = duration(value, unit, target=target, target_unit=target_unit)
    assert (r.score, r.status) == (0.0, CriterionStatus.FAIL)
    assert r.deviation.direction == "over"


# --- flexible durations ---------------------------------------------------------------------

def test_flexible_cross_unit_deviation_uses_day_ratio():
    # 7 months = 212 1/3 days vs 182 days -> d = 1/6 -> s = 1 - (1/6 / 0.25)^2 = 5/9
    r = duration(7, M, target=26, target_unit=W, flexibility="flexible")
    assert r.status == CriterionStatus.WARNING
    assert r.score == pytest.approx(5 / 9)
    assert r.deviation.relative == pytest.approx(1 / 6)


def test_flexible_cross_unit_small_overrun():
    # 28 weeks = 196 days vs 6 months = 182 days -> d = 1/13 -> s = 1 - (4/13)^2
    r = duration(28, W, target=6, target_unit=M, flexibility="flexible")
    assert r.score == pytest.approx(1 - (4 / 13) ** 2)
    assert not r.hard_failure


def test_flexible_cross_unit_beyond_tolerance_fails():
    r = duration(8, M, target=26, target_unit=W, flexibility="flexible")  # d = 1/3 >= 0.25
    assert (r.score, r.status, r.hard_failure) == (0.0, CriterionStatus.FAIL, True)


def test_flexible_same_unit_unchanged():
    r = duration(11, M, target=10, target_unit=M, flexibility="flexible")
    assert r.score == pytest.approx(0.84)


def test_flexible_cross_unit_equality_passes():
    r = duration(6, M, target=26, target_unit=W, flexibility="flexible")
    assert (r.score, r.status) == (1.0, CriterionStatus.PASS)
