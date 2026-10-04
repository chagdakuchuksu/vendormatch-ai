"""Evaluate one vendor against a project's materialized criteria."""

import math
from typing import Protocol, Sequence

from app.config import DEFAULT_SCORING_CONFIG, ScoringConfig
from app.errors import ScoringError
from app.schemas.analysis import CriterionResult, VendorAnalysis
from app.schemas.criterion import Criterion
from app.schemas.enums import FAILED_STATUSES, CriterionKind, CriterionStatus
from app.schemas.project import ProjectCreate
from app.schemas.vendor import VendorCreate
from app.services.scoring.aggregate import aggregate
from app.services.scoring.numeric import score_budget, score_duration, score_experience
from app.services.scoring.summary import compatibility_label, major_concerns, score_explanation, vendor_summary
from app.services.scoring.technology import score_technology
from app.utils.formatting import format_percent


class SemanticScorer(Protocol):
    """Scores a `text` criterion against a vendor proposal (implemented in M2)."""

    def __call__(self, criterion: Criterion, vendor: VendorCreate, config: ScoringConfig) -> CriterionResult: ...


def score_criterion(
    criterion: Criterion,
    project: ProjectCreate,
    vendor: VendorCreate,
    config: ScoringConfig = DEFAULT_SCORING_CONFIG,
    semantic_scorer: SemanticScorer | None = None,
) -> CriterionResult:
    match criterion.kind:
        case CriterionKind.BUDGET:
            return score_budget(criterion, project, vendor, config)
        case CriterionKind.DURATION:
            return score_duration(criterion, project, vendor, config)
        case CriterionKind.EXPERIENCE:
            return score_experience(criterion, vendor, config)
        case CriterionKind.TECHNOLOGY:
            return score_technology(criterion, vendor, config)
        case CriterionKind.TEXT:
            if semantic_scorer is None:
                raise ScoringError(f"Criterion '{criterion.name}' is a text criterion and needs a semantic scorer.")
            return semantic_scorer(criterion, vendor, config)
    raise ScoringError(f"Unsupported criterion kind: {criterion.kind}")


def evaluate_vendor(
    project: ProjectCreate,
    criteria: Sequence[Criterion],
    vendor: VendorCreate,
    *,
    config: ScoringConfig = DEFAULT_SCORING_CONFIG,
    semantic_scorer: SemanticScorer | None = None,
    vendor_id: int | None = None,
) -> VendorAnalysis:
    if not criteria:
        raise ScoringError("No criteria to evaluate.")
    if not math.isclose(math.fsum(c.normalized_weight for c in criteria), 1.0, abs_tol=1e-6):
        raise ScoringError("Criteria weights are not normalized; build them with build_criteria().")

    results = [score_criterion(c, project, vendor, config, semantic_scorer) for c in criteria]
    agg = aggregate(results)
    hard_failures = [r for r in results if r.hard_failure]
    overall = round(agg.overall_score, 1)
    concerns = _concerns(results, config)
    label = compatibility_label(overall, not hard_failures, config)

    return VendorAnalysis(
        vendor_id=vendor_id,
        vendor_name=vendor.name,
        overall_score=overall,
        base_score=round(agg.base_score, 1),
        hard_penalty_factor=round(agg.penalty_factor, 4),
        penalty_points=round(agg.base_score - agg.overall_score, 1),
        score_explanation=score_explanation(agg.base_score, agg.penalty_factor, overall, results),
        hard_requirements_met=not hard_failures,
        status_label=_status_label(results, hard_failures),
        compatibility_label=label,
        summary=vendor_summary(label, results, agg.penalty_factor),
        counts=agg.counts,
        criteria=results,
        missing_requirements=[r.name for r in results if r.status in FAILED_STATUSES],
        concerns=concerns,
        major_concerns=major_concerns(results, concerns),
        budget_deviation=_first_deviation(results, CriterionKind.BUDGET),
        duration_deviation=_first_deviation(results, CriterionKind.DURATION),
        technology_coverage=_technology_coverage(results),
    )


def _status_label(results: list[CriterionResult], hard_failures: list[CriterionResult]) -> str:
    if hard_failures:
        return "Hard requirement failed: " + ", ".join(r.name for r in hard_failures)
    if any(r.status != CriterionStatus.PASS for r in results):
        return "All hard requirements met, with warnings"
    return "All requirements met"


def _concerns(results: list[CriterionResult], config: ScoringConfig) -> list[str]:
    concerns = [f"{r.name}: {r.summary}" for r in results if r.status == CriterionStatus.WARNING]
    for r in results:
        dev = r.deviation
        if r.kind == CriterionKind.BUDGET and dev and dev.direction == "under" and dev.relative > config.low_bid_threshold:
            concerns.append(
                f"{r.name}: bid is {format_percent(dev.relative)} below the project budget — "
                "verify the proposal covers the full scope (informational, no score effect)."
            )
    return concerns


def _first_deviation(results: list[CriterionResult], kind: CriterionKind):
    return next((r.deviation for r in results if r.kind == kind), None)


def _technology_coverage(results: list[CriterionResult]) -> float | None:
    tech = [r for r in results if r.kind == CriterionKind.TECHNOLOGY]
    if not tech:
        return None
    return sum(r.status == CriterionStatus.PASS for r in tech) / len(tech)
