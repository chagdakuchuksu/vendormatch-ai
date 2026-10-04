"""Enumerations shared by schemas and the scoring engine."""

from enum import StrEnum


class Importance(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RequirementType(StrEnum):
    HARD = "hard"
    SOFT = "soft"


class Flexibility(StrEnum):
    STRICT = "strict"
    FLEXIBLE = "flexible"


class PenaltyCurve(StrEnum):
    """Shape of the penalty inside the tolerance zone of a flexible numeric criterion."""

    QUADRATIC = "quadratic"  # 1 - (d/tau)^2: small deviations cost little, large ones progressively more
    LINEAR = "linear"  # 1 - d/tau: every unit of deviation costs the same


class CriterionKind(StrEnum):
    BUDGET = "budget"
    DURATION = "duration"
    EXPERIENCE = "experience"
    TECHNOLOGY = "technology"
    TEXT = "text"


NUMERIC_KINDS = frozenset({CriterionKind.BUDGET, CriterionKind.DURATION, CriterionKind.EXPERIENCE})


class DurationUnit(StrEnum):
    WEEKS = "weeks"
    MONTHS = "months"


class CriterionStatus(StrEnum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    MISSING = "missing"


FAILED_STATUSES = frozenset({CriterionStatus.FAIL, CriterionStatus.MISSING})


class CriterionSource(StrEnum):
    USER = "user"
    AUTO = "auto"


class WeightSource(StrEnum):
    EXPLICIT = "explicit"
    IMPORTANCE_DEFAULT = "importance_default"
