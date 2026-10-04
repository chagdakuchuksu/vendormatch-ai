"""Combine criterion results into a vendor score.

base    = 100 * sum(normalized_weight_i * score_i)
penalty = product of hard_fail_factor(importance_i) over hard criteria that failed or are missing
overall = base * penalty
"""

import math
from dataclasses import dataclass
from typing import Sequence

from app.schemas.analysis import CriterionResult, RequirementCounts
from app.schemas.enums import CriterionStatus, RequirementType


@dataclass(frozen=True)
class AggregateScore:
    base_score: float
    penalty_factor: float
    overall_score: float
    counts: RequirementCounts


def aggregate(results: Sequence[CriterionResult]) -> AggregateScore:
    base = min(100.0, 100.0 * math.fsum(r.normalized_weight * r.score for r in results))
    penalty = math.prod(r.penalty_factor for r in results if r.hard_failure)
    return AggregateScore(
        base_score=base,
        penalty_factor=penalty,
        overall_score=base * penalty,
        counts=count_requirements(results),
    )


def count_requirements(results: Sequence[CriterionResult]) -> RequirementCounts:
    """Missing values count as failed."""
    counts = RequirementCounts()
    for r in results:
        prefix = "hard" if r.requirement_type == RequirementType.HARD else "soft"
        bucket = {CriterionStatus.PASS: "passed", CriterionStatus.WARNING: "warning"}.get(r.status, "failed")
        field = f"{prefix}_{bucket}"
        setattr(counts, field, getattr(counts, field) + 1)
    return counts
