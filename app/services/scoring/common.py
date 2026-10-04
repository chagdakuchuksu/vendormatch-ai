"""Helpers shared by the individual criterion scorers."""

from app.config import ScoringConfig
from app.schemas.analysis import CriterionResult, Deviation, SemanticEvidence
from app.schemas.criterion import Criterion
from app.schemas.enums import FAILED_STATUSES, CriterionStatus, RequirementType


def constraint_label(criterion: Criterion) -> str:
    """e.g. "Hard + Strict", "Soft + Flexible", "Hard"."""
    label = criterion.requirement_type.value.capitalize()
    if criterion.flexibility is not None:
        label += f" + {criterion.flexibility.value.capitalize()}"
    return label


def failure_consequence(criterion: Criterion, config: ScoringConfig) -> str:
    if criterion.requirement_type == RequirementType.HARD:
        factor = config.hard_fail_factors[criterion.importance]
        return (
            f"{constraint_label(criterion)} → failed hard requirement: criterion scores 0 and the "
            f"overall score is multiplied by {factor} ({criterion.importance.value} importance)."
        )
    return f"{constraint_label(criterion)} → criterion scores 0; vendor is not disqualified."


def make_result(
    criterion: Criterion,
    config: ScoringConfig,
    *,
    score: float,
    status: CriterionStatus,
    required_value: str,
    vendor_value: str,
    summary: str,
    explanation: str,
    deviation: Deviation | None = None,
    evidence: SemanticEvidence | None = None,
) -> CriterionResult:
    hard_failure = criterion.requirement_type == RequirementType.HARD and status in FAILED_STATUSES
    max_points = criterion.normalized_weight * 100
    return CriterionResult(
        criterion_id=criterion.id,
        name=criterion.name,
        kind=criterion.kind,
        requirement_type=criterion.requirement_type,
        importance=criterion.importance,
        flexibility=criterion.flexibility,
        normalized_weight=criterion.normalized_weight,
        score=score,
        max_points=max_points,
        contribution=max_points * score,
        points_lost=max_points * (1 - score),
        status=status,
        required_value=required_value,
        vendor_value=vendor_value,
        deviation=deviation,
        evidence=evidence,
        hard_failure=hard_failure,
        penalty_factor=config.hard_fail_factors[criterion.importance] if hard_failure else None,
        summary=summary,
        explanation=explanation,
    )
