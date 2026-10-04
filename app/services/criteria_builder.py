"""Turn a ProjectCreate into the complete, explicit list of criteria used for scoring.

This runs once when a project is created/updated, so the stored project always holds
every criterion (including auto-generated ones) with its weights already resolved.
"""

from app.config import DEFAULT_SCORING_CONFIG, AutoCriterionDefaults, ScoringConfig
from app.errors import InvalidCriteriaError
from app.schemas.criterion import CRITERION_INPUT_FIELDS, Criterion, CriterionIn
from app.schemas.enums import CriterionKind, CriterionSource, WeightSource
from app.schemas.project import ProjectCreate
from app.utils.text import normalize_technology, slugify
from app.utils.weights import normalize_weights


def build_criteria(project: ProjectCreate, config: ScoringConfig = DEFAULT_SCORING_CONFIG) -> list[Criterion]:
    _validate_user_criteria(project)

    # Criteria sent back from the API (CriterionUpdate) keep their source; plain inputs are "user".
    specs: list[tuple[CriterionIn, CriterionSource]] = [
        (c, getattr(c, "source", CriterionSource.USER)) for c in project.criteria
    ]
    user_kinds = {c.kind for c in project.criteria}

    if project.budget is not None and CriterionKind.BUDGET not in user_kinds:
        specs.append((_auto(config.auto_budget, "Budget", CriterionKind.BUDGET), CriterionSource.AUTO))
    if project.max_duration is not None and CriterionKind.DURATION not in user_kinds:
        specs.append((_auto(config.auto_duration, "Duration", CriterionKind.DURATION), CriterionSource.AUTO))

    covered = {normalize_technology(c.technology) for c in project.criteria if c.kind == CriterionKind.TECHNOLOGY}
    for tech in project.required_technologies:
        key = normalize_technology(tech)
        if key in covered:
            continue
        covered.add(key)
        specs.append(
            (_auto(config.auto_technology, tech, CriterionKind.TECHNOLOGY, technology=tech), CriterionSource.AUTO)
        )

    if not specs:
        raise InvalidCriteriaError("The project defines no criteria to evaluate vendors against.")

    effective = [_effective_weight(spec, config) for spec, _ in specs]
    normalized = normalize_weights([w for w, _ in effective])

    # Keep existing ids stable across updates; generate slugs for the rest.
    ids: set[str] = set()
    requested = [getattr(spec, "id", None) for spec, _ in specs]
    final_ids: list[str | None] = []
    for rid in requested:
        if rid and rid not in ids:
            ids.add(rid)
            final_ids.append(rid)
        else:
            final_ids.append(None)

    criteria = []
    for (spec, source), (weight, weight_source), norm, cid in zip(specs, effective, normalized, final_ids):
        criteria.append(
            Criterion(
                **spec.model_dump(include=CRITERION_INPUT_FIELDS),
                id=cid or _unique_id(spec.name, ids),
                source=source,
                weight_source=weight_source,
                effective_weight=weight,
                normalized_weight=norm,
            )
        )
    return criteria


def _effective_weight(spec: CriterionIn, config: ScoringConfig) -> tuple[float, WeightSource]:
    """Importance only supplies the default weight; an explicit weight always wins."""
    if spec.weight is not None:
        return spec.weight, WeightSource.EXPLICIT
    return config.default_weights[spec.importance], WeightSource.IMPORTANCE_DEFAULT


def _auto(defaults: AutoCriterionDefaults, name: str, kind: CriterionKind, **extra) -> CriterionIn:
    return CriterionIn(
        name=name,
        kind=kind,
        importance=defaults.importance,
        requirement_type=defaults.requirement_type,
        flexibility=defaults.flexibility,
        **extra,
    )


def _validate_user_criteria(project: ProjectCreate) -> None:
    errors: list[str] = []
    kinds = [c.kind for c in project.criteria]

    for kind, field in ((CriterionKind.BUDGET, "budget"), (CriterionKind.DURATION, "max_duration")):
        if kinds.count(kind) > 1:
            errors.append(f"Only one '{kind}' criterion is allowed.")
        if kind in kinds and getattr(project, field) is None:
            errors.append(f"A '{kind}' criterion requires the project '{field}' to be set.")

    seen: set[str] = set()
    for c in project.criteria:
        if c.kind != CriterionKind.TECHNOLOGY:
            continue
        key = normalize_technology(c.technology)
        if key in seen:
            errors.append(f"Technology '{c.technology}' has more than one criterion.")
        seen.add(key)

    required = [normalize_technology(t) for t in project.required_technologies]
    if len(required) != len(set(required)):
        errors.append("A required technology is listed more than once.")

    if errors:
        raise InvalidCriteriaError(" ".join(errors), {"errors": errors})


def _unique_id(name: str, used: set[str]) -> str:
    base = slugify(name)
    candidate, n = base, 2
    while candidate in used:
        candidate, n = f"{base}-{n}", n + 1
    used.add(candidate)
    return candidate
