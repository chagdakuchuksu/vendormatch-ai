"""Analysis output: per-criterion, per-vendor and per-project."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.enums import CriterionKind, CriterionStatus, Flexibility, Importance, RequirementType

RowStatus = Literal["pass", "warning", "fail"]


class Deviation(BaseModel):
    absolute: float  # |vendor - target|, in `unit`
    relative: float  # absolute / target
    unit: str  # "EUR", "months", "years", ...
    direction: Literal["over", "under", "none"]


class SemanticEvidence(BaseModel):
    requirement_text: str
    matched_text: str  # best-matching sentence (closest one, even when there is no match)
    source: str  # "proposal" or "previous project N"
    similarity: float  # raw cosine similarity
    normalized_score: float  # 0..1 after the threshold ramp
    strength: Literal["strong", "partial", "none"]
    lower_threshold: float
    upper_threshold: float


class CriterionResult(BaseModel):
    criterion_id: str
    name: str
    kind: CriterionKind
    requirement_type: RequirementType
    importance: Importance
    flexibility: Flexibility | None
    normalized_weight: float
    score: float  # 0..1
    max_points: float  # normalized_weight * 100: what this criterion can contribute
    contribution: float  # normalized_weight * score * 100 (points of the base score)
    points_lost: float  # max_points - contribution
    status: CriterionStatus
    required_value: str
    vendor_value: str
    deviation: Deviation | None = None
    evidence: SemanticEvidence | None = None
    hard_failure: bool
    penalty_factor: float | None = None  # set only when hard_failure is True
    summary: str  # short badge text, e.g. "€5,000 over budget"
    explanation: str  # full sentence(s) explaining the score


class RequirementCounts(BaseModel):
    hard_passed: int = 0
    hard_warning: int = 0
    hard_failed: int = 0
    soft_passed: int = 0
    soft_warning: int = 0
    soft_failed: int = 0


CompatibilityLabel = Literal[
    "Strong compatibility",
    "Mostly compatible with some concerns",
    "Requires review",
    "Hard requirement failed",
]


class VendorAnalysis(BaseModel):
    vendor_id: int | None = None
    vendor_name: str
    overall_score: float  # 0..100
    base_score: float  # 0..100, before hard-failure penalty
    hard_penalty_factor: float  # 1.0 when no hard requirement failed
    penalty_points: float  # base_score - overall_score
    score_explanation: str  # "Base 83.3 × 0.5 (Duration failed) = 41.7"
    hard_requirements_met: bool
    status_label: str
    compatibility_label: CompatibilityLabel  # neutral, descriptive; never a recommendation
    summary: str  # one or two neutral sentences
    counts: RequirementCounts
    criteria: list[CriterionResult]
    missing_requirements: list[str]
    concerns: list[str]
    major_concerns: list[str]  # hard failures, then unmet soft criteria, then warnings
    budget_deviation: Deviation | None = None
    duration_deviation: Deviation | None = None
    technology_coverage: float | None = None  # 0..1 share of technology criteria matched


DISCLAIMER = (
    "Decision support only. Scores reflect how each proposal matches the criteria and weights you "
    "defined; they are not a procurement decision. Review the evidence; the final decision stays with your team."
)
ORDERING_NOTE = "Vendors are listed by overall compatibility score. This order is a sorting aid, not a decision."


class ProjectAnalysis(BaseModel):
    project_id: int
    project_name: str
    scoring_version: str
    generated_at: datetime
    vendor_count: int
    vendors: list[VendorAnalysis]  # ordered by overall_score (desc), then vendor name
    ordering_note: str = ORDERING_NOTE
    disclaimer: str = DISCLAIMER


class ComparisonCriterion(BaseModel):
    """Column header information for a criterion-by-vendor matrix."""

    id: str
    name: str
    kind: CriterionKind
    importance: Importance
    requirement_type: RequirementType
    flexibility: Flexibility | None
    required_value: str
    normalized_weight: float
    max_points: float


class ComparisonCell(BaseModel):
    status: CriterionStatus
    score: float
    contribution: float
    vendor_value: str
    summary: str


class ComparisonRow(BaseModel):
    vendor_id: int
    vendor_name: str
    overall_score: float
    base_score: float
    hard_penalty_factor: float
    compatibility_label: CompatibilityLabel
    summary: str
    status: RowStatus  # fail = a hard requirement failed
    status_label: str
    # Hard requirements
    hard_requirements: str  # "100%", "Failed (1)" or "n/a"
    hard_requirements_passed: int
    hard_requirements_failed: int
    hard_requirements_total: int
    failed_hard_requirements: list[str]
    # Budget / duration
    budget: str  # "€55K" or "—"
    budget_value: float | None
    budget_status: CriterionStatus | None
    budget_summary: str | None
    duration: str  # "5 mo" or "—"
    duration_value: float | None
    duration_status: CriterionStatus | None
    duration_summary: str | None
    # Technology
    technology: str  # "67%" or "n/a"
    technology_coverage: float | None
    technology_status: RowStatus | None
    missing_technologies: list[str]
    # Semantic / text criteria
    semantic_status: RowStatus | None
    semantic_summary: str  # "1 strong, 1 partial of 2" or "n/a"
    semantic_score: float | None  # mean normalized score of text criteria
    # Concerns and per-criterion matrix
    major_concerns: list[str]
    cells: dict[str, ComparisonCell]  # keyed by criterion id


class ProjectComparison(BaseModel):
    project_id: int
    project_name: str
    scoring_version: str
    generated_at: datetime
    criteria: list[ComparisonCriterion]
    rows: list[ComparisonRow]  # same order as the analysis
    ordering_note: str = ORDERING_NOTE
    disclaimer: str = DISCLAIMER
