from fastapi import APIRouter, status

from app.api.deps import Config, Demo
from app.services.demo_service import DemoLoadResult

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health")
def health(config: Config) -> dict:
    return {"status": "ok", "scoring_version": config.version}


@router.post("/demo", response_model=DemoLoadResult, status_code=status.HTTP_201_CREATED)
def load_demo(demo: Demo) -> DemoLoadResult:
    """Create a fresh copy of the fictional demo project with three fictional vendors."""
    return demo.load()


@router.get("/scoring-model")
def scoring_model(config: Config) -> dict:
    """Every constant and formula used for scoring, for transparency."""
    return {
        "scoring_version": config.version,
        "formulas": {
            "effective_weight": "explicit weight if provided, otherwise default_weights[importance]",
            "normalized_weight": "effective_weight / sum(effective_weights)",
            "numeric_deviation": "upper bound: max(0, (v - T) / T); lower bound: max(0, (T - v) / T)",
            "numeric_score": "d = 0 -> 1; strict and d > 0 -> 0; flexible: 1 - (d / tolerance)^2 (quadratic, default) or 1 - d / tolerance (linear) if d < tolerance, else 0",
            "technology_score": "1 if the normalized technology name is listed by the vendor, else 0",
            "semantic_score": "clamp((cosine - lower) / (upper - lower), 0, 1)",
            "base_score": "100 * sum(normalized_weight * score)",
            "hard_penalty": "product of hard_fail_factors[importance] over failed or missing hard criteria",
            "overall_score": "base_score * hard_penalty",
        },
        "default_weights": dict(config.default_weights),
        "hard_fail_factors": dict(config.hard_fail_factors),
        "flexible_numeric": {"default_tolerance": config.default_tolerance, "configurable_per_criterion": True},
        "low_bid_concern": {"threshold": config.low_bid_threshold, "affects_score": False},
        "semantic": {
            "model": config.semantic_model_name,
            "runs_locally": True,
            "lower_threshold": config.semantic_lower,
            "upper_threshold": config.semantic_upper,
            "provisional": True,
            "note": "Provisional calibration constants, not scientifically validated. "
            "Semantic similarity only scores text criteria and never overrides numeric, technology or hard requirements. "
            "Known limitation: negated statements may still match.",
        },
        "auto_criteria": {
            name: {
                "importance": d.importance,
                "requirement_type": d.requirement_type,
                "flexibility": d.flexibility,
            }
            for name, d in (
                ("budget", config.auto_budget),
                ("duration", config.auto_duration),
                ("technology", config.auto_technology),
            )
        },
        "duration_conversion": {
            "strategy": "Different units are compared in days using exact rational arithmetic; same units are compared directly.",
            "days_per_week": 7,
            "days_per_month": "364/12 (30 1/3): 1/12 of a 52-week planning year",
            "examples": {"3 months": "91 days = 13 weeks", "6 months": "182 days = 26 weeks", "12 months": "364 days = 52 weeks"},
        },
    }
