"""Deterministic technology matching: normalized name lookup, no semantic similarity."""

from app.config import ScoringConfig
from app.schemas.analysis import CriterionResult
from app.schemas.criterion import Criterion
from app.schemas.enums import CriterionKind, CriterionStatus
from app.schemas.vendor import VendorCreate
from app.services.scoring.common import constraint_label, failure_consequence, make_result
from app.utils.text import normalize_technology


def score_technology(criterion: Criterion, vendor: VendorCreate, config: ScoringConfig) -> CriterionResult:
    if criterion.kind != CriterionKind.TECHNOLOGY:
        raise ValueError(f"expected a 'technology' criterion, got '{criterion.kind}'")

    required = criterion.technology
    key = normalize_technology(required)
    offered = {normalize_technology(t): t for t in vendor.technologies}

    if key in offered:
        return make_result(
            criterion,
            config,
            score=1.0,
            status=CriterionStatus.PASS,
            required_value=required,
            vendor_value=offered[key],
            summary="Listed by vendor",
            explanation=f"{required} is listed in the vendor's technologies ({constraint_label(criterion)}). Requirement met.",
        )

    if not vendor.technologies:
        return make_result(
            criterion,
            config,
            score=0.0,
            status=CriterionStatus.MISSING,
            required_value=required,
            vendor_value="no technologies listed",
            summary="Vendor listed no technologies",
            explanation=(
                f"The vendor listed no technologies, so {required} cannot be verified. "
                + failure_consequence(criterion, config)
            ),
        )

    return make_result(
        criterion,
        config,
        score=0.0,
        status=CriterionStatus.FAIL,
        required_value=required,
        vendor_value="not listed",
        summary="Not listed by vendor",
        explanation=(
            f"{required} is not in the vendor's technologies ({', '.join(vendor.technologies)}). "
            + failure_consequence(criterion, config)
        ),
    )
