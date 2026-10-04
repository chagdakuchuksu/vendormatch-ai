"""Small builders shared by the unit tests."""

from app.config import DEFAULT_SCORING_CONFIG, ScoringConfig
from app.schemas.analysis import CriterionResult
from app.schemas.criterion import Criterion, CriterionIn
from app.schemas.enums import CriterionKind, CriterionStatus, Flexibility, WeightSource
from app.schemas.project import ProjectCreate
from app.schemas.vendor import VendorCreate
from app.services.scoring.common import make_result
from app.utils.text import slugify


def criterion(kind: CriterionKind, *, normalized_weight: float = 1.0, **fields) -> Criterion:
    """A standalone materialized criterion (weight 1.0 unless given) for scorer tests."""
    fields.setdefault("name", kind.value.capitalize())
    if kind in (CriterionKind.BUDGET, CriterionKind.DURATION, CriterionKind.EXPERIENCE):
        fields.setdefault("flexibility", Flexibility.STRICT)
    spec = CriterionIn(kind=kind, **fields)
    return Criterion(
        **spec.model_dump(),
        id=slugify(spec.name),
        weight_source=WeightSource.EXPLICIT,
        effective_weight=normalized_weight,
        normalized_weight=normalized_weight,
    )


def project(**fields) -> ProjectCreate:
    fields.setdefault("name", "Test project")
    return ProjectCreate(**fields)


def vendor(**fields) -> VendorCreate:
    fields.setdefault("name", "Fictional Vendor")
    return VendorCreate(**fields)


def spec_example_project() -> ProjectCreate:
    """The example from the product spec (section 2)."""
    return project(
        name="E-commerce Mobile Application",
        budget=50_000,
        currency="EUR",
        max_duration=6,
        required_technologies=["React Native", "Node.js", "PostgreSQL"],
        criteria=[
            CriterionIn(name="Duration", kind="duration", importance="critical", requirement_type="hard", flexibility="strict"),
            CriterionIn(name="Budget", kind="budget", importance="high", requirement_type="soft", flexibility="flexible"),
            CriterionIn(name="React Native", kind="technology", technology="React Native", importance="critical", requirement_type="hard"),
            CriterionIn(
                name="E-commerce experience",
                kind="text",
                description="Previous e-commerce experience",
                importance="high",
                requirement_type="soft",
            ),
            CriterionIn(
                name="Company experience",
                kind="experience",
                min_value=5,
                importance="medium",
                requirement_type="soft",
                flexibility="flexible",
            ),
        ],
    )


class FixedSemanticScorer:
    """Stand-in for the M2 semantic scorer: returns a fixed score for every text criterion."""

    def __init__(self, score: float = 1.0):
        self.score = score

    def __call__(self, crit: Criterion, vendor: VendorCreate, config: ScoringConfig = DEFAULT_SCORING_CONFIG) -> CriterionResult:
        status = CriterionStatus.PASS if self.score >= 1 else CriterionStatus.WARNING if self.score > 0 else CriterionStatus.FAIL
        return make_result(
            crit,
            config,
            score=self.score,
            status=status,
            required_value=crit.description or crit.name,
            vendor_value="(fixed test score)",
            summary="fixed",
            explanation="Fixed semantic score for tests.",
        )
