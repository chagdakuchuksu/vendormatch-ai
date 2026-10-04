"""Semantic scoring of `text` criteria.

Only `text` criteria are ever routed here (see engine.score_criterion). The result is an
ordinary CriterionResult for that one criterion, so it cannot change budget, duration,
experience or technology results, nor any other criterion's hard-requirement outcome.
"""

from app.config import ScoringConfig
from app.schemas.analysis import CriterionResult, SemanticEvidence
from app.schemas.criterion import Criterion
from app.schemas.enums import CriterionKind, CriterionStatus
from app.schemas.vendor import VendorCreate
from app.services.scoring.common import constraint_label, failure_consequence, make_result
from app.services.semantic.embedder import Embedder
from app.services.semantic.matcher import best_match, evidence_chunks, requirement_text, similarity_to_score

_STATUS = {"strong": CriterionStatus.PASS, "partial": CriterionStatus.WARNING, "none": CriterionStatus.FAIL}
_SUMMARY = {"strong": "Strong semantic match", "partial": "Partial semantic match", "none": "No relevant evidence found"}


class SemanticCriterionScorer:
    """Implements the engine's SemanticScorer protocol using an Embedder."""

    def __init__(self, embedder: Embedder):
        self.embedder = embedder

    def __call__(self, criterion: Criterion, vendor: VendorCreate, config: ScoringConfig) -> CriterionResult:
        if criterion.kind != CriterionKind.TEXT:
            raise ValueError(f"semantic scoring only applies to 'text' criteria, got '{criterion.kind}'")

        requirement = requirement_text(criterion)
        chunks = evidence_chunks(vendor)
        if not chunks:
            return make_result(
                criterion,
                config,
                score=0.0,
                status=CriterionStatus.MISSING,
                required_value=requirement,
                vendor_value="no proposal text",
                summary="No proposal text to compare",
                explanation=(
                    "The vendor provided no proposal text or previous projects, so the requirement cannot be "
                    "assessed. " + failure_consequence(criterion, config)
                ),
            )

        match = best_match(requirement, chunks, self.embedder)
        lower, upper = config.semantic_lower, config.semantic_upper
        score, strength = similarity_to_score(match.similarity, lower, upper)
        status = _STATUS[strength]

        evidence = SemanticEvidence(
            requirement_text=requirement,
            matched_text=match.chunk.text,
            source=match.chunk.source,
            similarity=round(match.similarity, 4),
            normalized_score=score,
            strength=strength,
            lower_threshold=lower,
            upper_threshold=upper,
        )
        label = "Matched evidence" if strength != "none" else "Closest sentence"
        explanation = (
            f'{label} ({match.chunk.source}): "{match.chunk.text}" — cosine similarity {match.similarity:.2f} '
            f"(≤ {lower:.2f} no match, ≥ {upper:.2f} strong; provisional thresholds). "
        )
        if strength == "strong":
            explanation += "Strong semantic match → full score."
        elif strength == "partial":
            explanation += f"{constraint_label(criterion)}: partial semantic match → score {score:.2f}."
        else:
            explanation += "No sufficiently related statement found. " + failure_consequence(criterion, config)

        return make_result(
            criterion,
            config,
            score=score,
            status=status,
            required_value=requirement,
            vendor_value=match.chunk.text,
            evidence=evidence,
            summary=f"{_SUMMARY[strength]} ({match.similarity:.2f})",
            explanation=explanation,
        )
