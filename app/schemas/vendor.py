from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import DurationUnit


class VendorCreate(BaseModel):
    """A vendor proposal. Budgets are in the project's currency (no FX conversion in the MVP)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    proposed_budget: float | None = Field(None, gt=0, allow_inf_nan=False)
    proposed_duration: float | None = Field(None, gt=0, allow_inf_nan=False)
    duration_unit: DurationUnit = DurationUnit.MONTHS
    years_experience: float | None = Field(None, ge=0, allow_inf_nan=False)
    technologies: list[str] = Field(default_factory=list, max_length=50)
    proposal_text: str = Field("", max_length=10000)
    previous_projects: list[str] = Field(default_factory=list, max_length=50)


class Vendor(VendorCreate):
    id: int
    project_id: int
    is_demo: bool = False
    created_at: datetime
    updated_at: datetime
