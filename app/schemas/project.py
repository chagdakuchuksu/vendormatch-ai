from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.criterion import Criterion, CriterionIn, CriterionUpdate
from app.schemas.enums import DurationUnit


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    description: str = Field("", max_length=5000)
    budget: float | None = Field(None, gt=0, allow_inf_nan=False)
    currency: str = Field("EUR", pattern=r"^[A-Z]{3}$")
    max_duration: float | None = Field(None, gt=0, allow_inf_nan=False)
    duration_unit: DurationUnit = DurationUnit.MONTHS
    required_technologies: list[str] = Field(default_factory=list, max_length=50)
    criteria: list[CriterionIn] = Field(default_factory=list, max_length=100)

    @field_validator("required_technologies")
    @classmethod
    def _strip_technologies(cls, value: list[str]) -> list[str]:
        cleaned = [t.strip() for t in value]
        if any(not t for t in cleaned):
            raise ValueError("required technologies must not be blank")
        return cleaned


class ProjectUpdate(ProjectCreate):
    """Full replacement (PUT). Criteria may be sent back exactly as returned by GET."""

    criteria: list[CriterionUpdate] = Field(default_factory=list, max_length=100)


class Project(ProjectCreate):
    id: int
    criteria: list[Criterion]
    is_demo: bool = False
    created_at: datetime
    updated_at: datetime


class ProjectSummary(BaseModel):
    id: int
    name: str
    is_demo: bool
    vendor_count: int
    criteria_count: int
    created_at: datetime
    updated_at: datetime
