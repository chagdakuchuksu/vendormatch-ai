from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.enums import (
    NUMERIC_KINDS,
    CriterionKind,
    CriterionSource,
    Flexibility,
    Importance,
    PenaltyCurve,
    RequirementType,
    WeightSource,
)


class CriterionIn(BaseModel):
    """A user-defined evaluation criterion.

    Field rules by kind:
    - budget / duration: ``flexibility`` required; target comes from the project.
    - experience: ``flexibility`` and ``min_value`` (years) required.
    - technology: ``technology`` required.
    - text: ``description`` required (evaluated semantically, M2).
    ``tolerance`` and ``curve`` are only allowed for flexible numeric criteria.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    kind: CriterionKind
    description: str | None = Field(None, max_length=1000)
    importance: Importance = Importance.MEDIUM
    requirement_type: RequirementType = RequirementType.SOFT
    flexibility: Flexibility | None = None
    tolerance: float | None = Field(None, gt=0, le=1)
    curve: PenaltyCurve | None = None  # flexible numeric only; default quadratic
    weight: float | None = Field(None, ge=0, allow_inf_nan=False)
    min_value: float | None = Field(None, gt=0, allow_inf_nan=False)
    technology: str | None = Field(None, max_length=100)

    @model_validator(mode="after")
    def _check_kind_fields(self):
        errors: list[str] = []
        numeric = self.kind in NUMERIC_KINDS

        if numeric and self.flexibility is None:
            errors.append(f"'{self.kind}' criteria require 'flexibility' (strict or flexible)")
        if not numeric and self.flexibility is not None:
            errors.append(f"'flexibility' only applies to numeric criteria, not '{self.kind}'")
        if self.tolerance is not None and self.flexibility != Flexibility.FLEXIBLE:
            errors.append("'tolerance' is only allowed for flexible numeric criteria")
        if self.curve is not None and self.flexibility != Flexibility.FLEXIBLE:
            errors.append("'curve' is only allowed for flexible numeric criteria")

        if self.kind == CriterionKind.EXPERIENCE and self.min_value is None:
            errors.append("'experience' criteria require 'min_value' (years)")
        if self.kind != CriterionKind.EXPERIENCE and self.min_value is not None:
            errors.append("'min_value' only applies to 'experience' criteria")

        if self.kind == CriterionKind.TECHNOLOGY and not (self.technology or "").strip():
            errors.append("'technology' criteria require a non-empty 'technology'")
        if self.kind != CriterionKind.TECHNOLOGY and self.technology is not None:
            errors.append("'technology' only applies to 'technology' criteria")

        if self.kind == CriterionKind.TEXT and not (self.description or "").strip():
            errors.append("'text' criteria require a non-empty 'description'")

        if errors:
            raise ValueError("; ".join(errors))
        return self


class CriterionUpdate(CriterionIn):
    """Criterion input for project updates.

    Accepts a criterion exactly as returned by the API, so clients can edit and send back the
    full list (including auto-generated criteria). `id` and `source` are kept; the weight fields
    are read-only and always recomputed by the criteria builder.
    """

    id: str | None = Field(None, max_length=120)
    source: CriterionSource = CriterionSource.USER
    weight_source: WeightSource | None = None
    effective_weight: float | None = None
    normalized_weight: float | None = None


CRITERION_INPUT_FIELDS = frozenset(CriterionIn.model_fields)


class Criterion(CriterionIn):
    """A materialized criterion as stored on a project and used for scoring."""

    id: str
    source: CriterionSource = CriterionSource.USER
    weight_source: WeightSource
    effective_weight: float = Field(ge=0)
    normalized_weight: float = Field(ge=0, le=1)
