"""Compute analyses from the current stored data. Nothing here is persisted."""

import sqlite3
from datetime import datetime, timezone

from app.config import DEFAULT_SCORING_CONFIG, ScoringConfig
from app.data.repositories import ProjectRepository, VendorRepository
from app.errors import NotFoundError
from app.schemas.analysis import (
    ComparisonCell,
    ComparisonCriterion,
    ComparisonRow,
    CriterionResult,
    ProjectAnalysis,
    ProjectComparison,
    RowStatus,
    VendorAnalysis,
)
from app.schemas.criterion import Criterion
from app.schemas.enums import FAILED_STATUSES, CriterionKind, CriterionStatus, RequirementType
from app.schemas.project import Project
from app.schemas.vendor import Vendor
from app.services.scoring.engine import SemanticScorer, evaluate_vendor
from app.utils.formatting import format_duration_short, format_money, format_money_short, format_quantity


class AnalysisService:
    def __init__(
        self,
        conn: sqlite3.Connection,
        semantic_scorer: SemanticScorer | None,
        config: ScoringConfig = DEFAULT_SCORING_CONFIG,
    ):
        self.projects = ProjectRepository(conn)
        self.vendors = VendorRepository(conn)
        self.semantic_scorer = semantic_scorer
        self.config = config

    def analyze(self, project_id: int) -> ProjectAnalysis:
        project, vendors = self._load(project_id)
        return self._analyze(project, vendors)

    def compare(self, project_id: int) -> ProjectComparison:
        project, vendors = self._load(project_id)
        analysis = self._analyze(project, vendors)
        by_id = {v.id: v for v in vendors}
        return ProjectComparison(
            project_id=project.id,
            project_name=project.name,
            scoring_version=analysis.scoring_version,
            generated_at=analysis.generated_at,
            criteria=[comparison_criterion(c, project) for c in project.criteria],
            rows=[comparison_row(a, by_id[a.vendor_id], project) for a in analysis.vendors],
        )

    def _load(self, project_id: int) -> tuple[Project, list[Vendor]]:
        project = self.projects.get(project_id)
        if project is None:
            raise NotFoundError(f"Project {project_id} not found.", {"project_id": project_id})
        return project, self.vendors.list_for_project(project_id)

    def _analyze(self, project: Project, vendors: list[Vendor]) -> ProjectAnalysis:
        results = [
            evaluate_vendor(
                project, project.criteria, v, config=self.config, semantic_scorer=self.semantic_scorer, vendor_id=v.id
            )
            for v in vendors
        ]
        # Ordered by score for readability; every vendor is always included.
        results.sort(key=lambda a: (-a.overall_score, a.vendor_name.lower(), a.vendor_id))
        return ProjectAnalysis(
            project_id=project.id,
            project_name=project.name,
            scoring_version=self.config.version,
            generated_at=datetime.now(timezone.utc),
            vendor_count=len(results),
            vendors=results,
        )


# --- comparison helpers ---------------------------------------------------------------------

def required_value(criterion: Criterion, project: Project) -> str:
    match criterion.kind:
        case CriterionKind.BUDGET:
            return f"≤ {format_money(project.budget, project.currency)}"
        case CriterionKind.DURATION:
            return f"≤ {format_quantity(project.max_duration, project.duration_unit.value)}"
        case CriterionKind.EXPERIENCE:
            return f"≥ {format_quantity(criterion.min_value, 'years')}"
        case CriterionKind.TECHNOLOGY:
            return criterion.technology
        case _:
            return criterion.description or criterion.name


def comparison_criterion(criterion: Criterion, project: Project) -> ComparisonCriterion:
    return ComparisonCriterion(
        id=criterion.id,
        name=criterion.name,
        kind=criterion.kind,
        importance=criterion.importance,
        requirement_type=criterion.requirement_type,
        flexibility=criterion.flexibility,
        required_value=required_value(criterion, project),
        normalized_weight=criterion.normalized_weight,
        max_points=criterion.normalized_weight * 100,
    )


def group_status(results: list[CriterionResult]) -> RowStatus | None:
    """fail if a hard criterion failed; warning if any other criterion is not fully met; else pass."""
    if not results:
        return None
    if any(r.hard_failure for r in results):
        return "fail"
    if any(r.status != CriterionStatus.PASS for r in results):
        return "warning"
    return "pass"


def semantic_summary(results: list[CriterionResult]) -> str:
    if not results:
        return "n/a"
    strengths = [r.evidence.strength if r.evidence else "none" for r in results]
    parts = [f"{strengths.count(s)} {s}" for s in ("strong", "partial", "none") if strengths.count(s)]
    return f"{', '.join(parts)} of {len(results)}"


def comparison_row(analysis: VendorAnalysis, vendor: Vendor, project: Project) -> ComparisonRow:
    results = analysis.criteria
    of_kind = lambda kind: [r for r in results if r.kind == kind]  # noqa: E731
    first = lambda kind: next(iter(of_kind(kind)), None)  # noqa: E731

    hard = [r for r in results if r.requirement_type == RequirementType.HARD]
    hard_failed = [r for r in hard if r.hard_failure]
    if not hard:
        hard_label = "n/a"
    elif hard_failed:
        hard_label = f"Failed ({len(hard_failed)})"
    else:
        hard_label = "100%"

    tech, text = of_kind(CriterionKind.TECHNOLOGY), of_kind(CriterionKind.TEXT)
    budget, duration = first(CriterionKind.BUDGET), first(CriterionKind.DURATION)
    coverage = analysis.technology_coverage

    return ComparisonRow(
        vendor_id=vendor.id,
        vendor_name=vendor.name,
        overall_score=analysis.overall_score,
        base_score=analysis.base_score,
        hard_penalty_factor=analysis.hard_penalty_factor,
        compatibility_label=analysis.compatibility_label,
        summary=analysis.summary,
        status=group_status(results) or "pass",
        status_label=analysis.status_label,
        hard_requirements=hard_label,
        hard_requirements_passed=len(hard) - len(hard_failed),
        hard_requirements_failed=len(hard_failed),
        hard_requirements_total=len(hard),
        failed_hard_requirements=[r.name for r in hard_failed],
        budget=format_money_short(vendor.proposed_budget, project.currency) if vendor.proposed_budget else "—",
        budget_value=vendor.proposed_budget,
        budget_status=budget.status if budget else None,
        budget_summary=budget.summary if budget else None,
        duration=(
            format_duration_short(vendor.proposed_duration, vendor.duration_unit.value)
            if vendor.proposed_duration
            else "—"
        ),
        duration_value=vendor.proposed_duration,
        duration_status=duration.status if duration else None,
        duration_summary=duration.summary if duration else None,
        technology=f"{coverage:.0%}" if coverage is not None else "n/a",
        technology_coverage=coverage,
        technology_status=group_status(tech),
        missing_technologies=[r.name for r in tech if r.status in FAILED_STATUSES],
        semantic_status=group_status(text),
        semantic_summary=semantic_summary(text),
        semantic_score=sum(r.score for r in text) / len(text) if text else None,
        major_concerns=analysis.major_concerns,
        cells={
            r.criterion_id: ComparisonCell(
                status=r.status, score=r.score, contribution=r.contribution, vendor_value=r.vendor_value, summary=r.summary
            )
            for r in results
        },
    )
