"""Deterministic scoring for numeric criteria: budget, duration, experience.

d = relative deviation in the unfavourable direction (0 when the requirement is met)
    upper bound (budget, duration):  d = max(0, (v - T) / T)
    lower bound (experience):        d = max(0, (T - v) / T)

d = 0                    -> s = 1              pass
Strict,   d > 0          -> s = 0              fail
Flexible, 0 < d < tau    -> s = 1 - (d/tau)^2  warning   (curve "quadratic", the default)
                            s = 1 - d/tau      warning   (curve "linear")
Flexible, d >= tau       -> s = 0              fail
vendor value missing     -> s = 0              missing
"""

from dataclasses import dataclass
from typing import Callable

from app.config import ScoringConfig
from app.schemas.analysis import CriterionResult, Deviation
from app.schemas.criterion import Criterion
from app.schemas.enums import CriterionKind, CriterionStatus, Flexibility, PenaltyCurve
from app.schemas.project import ProjectCreate
from app.schemas.vendor import VendorCreate
from app.services.scoring.common import constraint_label, failure_consequence, make_result
from app.utils.formatting import format_money, format_percent, format_quantity
from app.utils.units import convert_duration

_EPSILON = 1e-9


def score_deviation(
    d: float, flexibility: Flexibility, tolerance: float, curve: PenaltyCurve = PenaltyCurve.QUADRATIC
) -> tuple[float, CriterionStatus]:
    """Core curve: map a non-negative relative deviation to (score, status)."""
    if d < 0:
        raise ValueError("deviation must be non-negative")
    if tolerance <= 0:
        raise ValueError("tolerance must be positive")
    if d <= _EPSILON:
        return 1.0, CriterionStatus.PASS
    if flexibility == Flexibility.STRICT or d >= tolerance:
        return 0.0, CriterionStatus.FAIL
    ratio = d / tolerance
    score = 1.0 - ratio if curve == PenaltyCurve.LINEAR else 1.0 - ratio**2
    return score, CriterionStatus.WARNING


def resolve_tolerance(criterion: Criterion, config: ScoringConfig) -> float:
    return criterion.tolerance if criterion.tolerance is not None else config.default_tolerance


@dataclass(frozen=True)
class _Bound:
    """How to evaluate and describe one numeric bound."""

    target: float
    upper: bool  # True: vendor must not exceed target; False: vendor must reach target
    unit: str
    fmt: Callable[[float], str]
    target_phrase: str  # "maximum budget of €50,000"
    over_word: str  # summary wording when the vendor value is above the target
    under_word: str  # ... and when below
    subject: str  # used when the value is missing, e.g. "a budget"


def score_budget(
    criterion: Criterion, project: ProjectCreate, vendor: VendorCreate, config: ScoringConfig
) -> CriterionResult:
    _require_kind(criterion, CriterionKind.BUDGET)
    if project.budget is None:
        raise ValueError("budget criterion requires project.budget")

    def fmt(x: float) -> str:
        return format_money(x, project.currency)

    preferred = "preferred " if criterion.flexibility == Flexibility.FLEXIBLE else ""
    bound = _Bound(
        target=project.budget,
        upper=True,
        unit=project.currency,
        fmt=fmt,
        target_phrase=f"{preferred}maximum budget of {fmt(project.budget)}",
        over_word="over budget",
        under_word="under budget",
        subject="a budget",
    )
    vendor_value = fmt(vendor.proposed_budget) if vendor.proposed_budget is not None else None
    return _score_bound(criterion, config, bound, vendor.proposed_budget, vendor_value)


def score_duration(
    criterion: Criterion, project: ProjectCreate, vendor: VendorCreate, config: ScoringConfig
) -> CriterionResult:
    _require_kind(criterion, CriterionKind.DURATION)
    if project.max_duration is None:
        raise ValueError("duration criterion requires project.max_duration")

    unit = project.duration_unit.value

    def fmt(x: float) -> str:
        return format_quantity(x, unit)

    value = vendor_value = None
    if vendor.proposed_duration is not None:
        # Different units are normalized through days (exact; see app/utils/units.py).
        value = convert_duration(vendor.proposed_duration, vendor.duration_unit, project.duration_unit)
        vendor_value = format_quantity(vendor.proposed_duration, vendor.duration_unit.value)
        if vendor.duration_unit != project.duration_unit:
            vendor_value += f" (≈ {fmt(value)})"

    strict = criterion.flexibility == Flexibility.STRICT
    bound = _Bound(
        target=project.max_duration,
        upper=True,
        unit=unit,
        fmt=fmt,
        target_phrase=f"{'strict' if strict else 'preferred'} maximum duration of {fmt(project.max_duration)}",
        over_word="over the strict deadline" if strict else "over the preferred duration",
        under_word="ahead of the maximum duration",
        subject="a duration",
    )
    return _score_bound(criterion, config, bound, value, vendor_value)


def score_experience(criterion: Criterion, vendor: VendorCreate, config: ScoringConfig) -> CriterionResult:
    _require_kind(criterion, CriterionKind.EXPERIENCE)

    def fmt(x: float) -> str:
        return format_quantity(x, "years")

    bound = _Bound(
        target=criterion.min_value,
        upper=False,
        unit="years",
        fmt=fmt,
        target_phrase=f"minimum of {fmt(criterion.min_value)}",
        over_word="above the minimum",
        under_word="below the minimum",
        subject="its years of experience",
    )
    value = vendor.years_experience
    return _score_bound(criterion, config, bound, value, fmt(value) if value is not None else None)


def _score_bound(
    criterion: Criterion, config: ScoringConfig, bound: _Bound, value: float | None, vendor_value: str | None
) -> CriterionResult:
    required_value = f"{'≤' if bound.upper else '≥'} {bound.fmt(bound.target)}"

    if value is None:
        return make_result(
            criterion,
            config,
            score=0.0,
            status=CriterionStatus.MISSING,
            required_value=required_value,
            vendor_value="not stated",
            summary="Not stated by vendor",
            explanation=(
                f"The vendor did not state {bound.subject}, so the requirement cannot be verified. "
                + failure_consequence(criterion, config)
            ),
        )

    diff = value - bound.target
    if abs(diff) <= _EPSILON * max(1.0, abs(bound.target)):
        diff = 0.0
    unfavourable = diff if bound.upper else -diff
    d = max(0.0, unfavourable / bound.target)
    tolerance = resolve_tolerance(criterion, config)
    curve = criterion.curve or PenaltyCurve.QUADRATIC
    score, status = score_deviation(d, criterion.flexibility, tolerance, curve)

    relative = abs(diff) / bound.target
    direction = "over" if diff > 0 else "under" if diff < 0 else "none"
    deviation = Deviation(absolute=abs(diff), relative=relative, unit=bound.unit, direction=direction)

    if direction == "none":
        comparison = f"{vendor_value} matches the {bound.target_phrase}."
        summary = "Meets requirement exactly"
    else:
        side = "above" if direction == "over" else "below"
        amount = f"{bound.fmt(abs(diff))} ({format_percent(relative)})"
        comparison = f"{vendor_value} is {amount} {side} the {bound.target_phrase}."
        summary = f"{bound.fmt(abs(diff))} {bound.over_word if direction == 'over' else bound.under_word}"

    if status == CriterionStatus.PASS:
        outcome = "Requirement met."
    elif status == CriterionStatus.WARNING:
        outcome = (
            f"{constraint_label(criterion)}: within the {format_percent(tolerance)} tolerance → partial score "
            f"{score:.2f} ("
            + ("penalty grows in proportion to the deviation" if curve == PenaltyCurve.LINEAR
               else "penalty grows quadratically with the deviation")
            + ")."
        )
    elif criterion.flexibility == Flexibility.FLEXIBLE:
        outcome = (
            f"Deviation exceeds the {format_percent(tolerance)} tolerance. " + failure_consequence(criterion, config)
        )
    else:
        outcome = failure_consequence(criterion, config)

    return make_result(
        criterion,
        config,
        score=score,
        status=status,
        required_value=required_value,
        vendor_value=vendor_value,
        deviation=deviation,
        summary=summary,
        explanation=f"{comparison} {outcome}",
    )


def _require_kind(criterion: Criterion, kind: CriterionKind) -> None:
    if criterion.kind != kind:
        raise ValueError(f"expected a '{kind}' criterion, got '{criterion.kind}'")
