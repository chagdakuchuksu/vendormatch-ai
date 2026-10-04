"""Neutral, deterministic wording for vendor results.

These texts describe the analysis; they never recommend or select a vendor and never
change a score. Label thresholds live in ScoringConfig (presentation only).
"""

from typing import Sequence

from app.config import ScoringConfig
from app.schemas.analysis import CompatibilityLabel, CriterionResult
from app.schemas.enums import FAILED_STATUSES, CriterionStatus, RequirementType


def compatibility_label(overall_score: float, hard_requirements_met: bool, config: ScoringConfig) -> CompatibilityLabel:
    if not hard_requirements_met:
        return "Hard requirement failed"
    if overall_score >= config.label_strong_min:
        return "Strong compatibility"
    if overall_score >= config.label_mostly_min:
        return "Mostly compatible with some concerns"
    return "Requires review"


def major_concerns(results: Sequence[CriterionResult], concerns: Sequence[str]) -> list[str]:
    """Hard failures first, then unmet soft criteria, then warnings and informational notes."""
    items = [f"{r.name}: {r.summary} (hard requirement)" for r in results if r.hard_failure]
    items += [f"{r.name}: {r.summary}" for r in results if r.status in FAILED_STATUSES and not r.hard_failure]
    items += [c for c in concerns if c not in items]
    return items


def vendor_summary(label: CompatibilityLabel, results: Sequence[CriterionResult], penalty_factor: float) -> str:
    hard = [r for r in results if r.requirement_type == RequirementType.HARD]
    hard_failed = [r for r in hard if r.hard_failure]
    soft_unmet = [r.name for r in results if r.status in FAILED_STATUSES and not r.hard_failure]
    warnings = [r.name for r in results if r.status == CriterionStatus.WARNING]

    if hard_failed:
        failed = "; ".join(f"{r.name} ({r.summary})" for r in hard_failed)
        text = (
            f"{label}: {failed}. The overall score is multiplied by {penalty_factor:g}; "
            "the vendor remains in the comparison for review."
        )
        if soft_unmet:
            text += f" Also not met: {', '.join(soft_unmet)}."
        return text

    parts = [f"meets all {len(hard)} hard requirements" if hard else "no hard requirements defined"]
    if soft_unmet:
        parts.append(f"not met: {', '.join(soft_unmet)}")
    if warnings:
        parts.append(f"partially met: {', '.join(warnings)}")
    return f"{label}: {'; '.join(parts)}."


def score_explanation(base_score: float, penalty_factor: float, overall_score: float, results: Sequence[CriterionResult]) -> str:
    base = f"Base score {base_score:.2f} (sum of weighted criterion scores)"
    failed = [r for r in results if r.hard_failure]
    if not failed:
        return f"{base}; no hard requirement failed, so the overall score is {overall_score:.1f}."
    factors = ", ".join(f"{r.name} ×{r.penalty_factor:g}" for r in failed)
    return (
        f"{base} × hard-fail multiplier {penalty_factor:g} ({factors}) = {base_score * penalty_factor:.2f}, "
        f"shown as {overall_score:.1f}."
    )
