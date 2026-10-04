"""Application configuration.

Every constant that influences a score lives in ``ScoringConfig`` so the model is
documented in one place and can be exposed verbatim through the API.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from app.schemas.enums import Flexibility, Importance, RequirementType


def _frozen(mapping: dict) -> Mapping:
    return MappingProxyType(mapping)


@dataclass(frozen=True)
class AutoCriterionDefaults:
    """Defaults for criteria generated from project-level fields."""

    importance: Importance
    requirement_type: RequirementType
    flexibility: Flexibility | None = None


@dataclass(frozen=True)
class ScoringConfig:
    # Bump whenever any constant below changes; it is reported with every analysis.
    # 1.1: cross-unit durations are compared through days (1 month = 30 1/3 days).
    # 1.2: optional linear penalty curve for flexible numeric criteria (default stays quadratic).
    version: str = "1.2"

    # Importance -> default raw weight. Used ONLY when a criterion has no explicit weight.
    default_weights: Mapping[Importance, float] = field(
        default_factory=lambda: _frozen(
            {Importance.CRITICAL: 4.0, Importance.HIGH: 3.0, Importance.MEDIUM: 2.0, Importance.LOW: 1.0}
        )
    )

    # Importance -> multiplier applied to the overall score for each failed HARD criterion.
    hard_fail_factors: Mapping[Importance, float] = field(
        default_factory=lambda: _frozen(
            {Importance.CRITICAL: 0.5, Importance.HIGH: 0.6, Importance.MEDIUM: 0.7, Importance.LOW: 0.8}
        )
    )

    # Flexible numeric criteria: relative deviation at which the score reaches 0.
    default_tolerance: float = 0.25

    # A bid this far below the budget (relative) adds an informational concern. No score effect.
    low_bid_threshold: float = 0.40

    # Provisional calibration constants for cosine similarity (not scientifically validated).
    # See docs/M2-calibration.md. similarity <= lower -> 0, >= upper -> 1, linear in between.
    semantic_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    semantic_lower: float = 0.30
    semantic_upper: float = 0.60

    # Presentation only (never change a score): minimum overall score for the neutral labels
    # "Strong compatibility" and "Mostly compatible with some concerns" when all hard
    # requirements are met; below that: "Requires review".
    label_strong_min: float = 85.0
    label_mostly_min: float = 65.0

    # Duration units are compared through days: see app/utils/units.py
    # (1 week = 7 days, 1 month = 364/12 = 30 1/3 days, exact rational arithmetic).

    auto_budget: AutoCriterionDefaults = AutoCriterionDefaults(
        Importance.HIGH, RequirementType.SOFT, Flexibility.FLEXIBLE
    )
    auto_duration: AutoCriterionDefaults = AutoCriterionDefaults(
        Importance.HIGH, RequirementType.HARD, Flexibility.STRICT
    )
    # Project-level "required technologies" are explicitly required by the company.
    auto_technology: AutoCriterionDefaults = AutoCriterionDefaults(Importance.CRITICAL, RequirementType.HARD)

    def __post_init__(self):
        if not 0 < self.default_tolerance <= 1:
            raise ValueError("default_tolerance must be in (0, 1]")
        if not -1 <= self.semantic_lower < self.semantic_upper <= 1:
            raise ValueError("semantic thresholds must satisfy -1 <= lower < upper <= 1")


DEFAULT_SCORING_CONFIG = ScoringConfig()

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    """Runtime settings, read from environment variables by `from_env()`."""

    db_path: Path = PROJECT_ROOT / "instance" / "vendormatch.db"
    examples_dir: Path = PROJECT_ROOT / "examples"
    # Older demo copies beyond this many are pruned when a new demo is loaded.
    max_demo_projects: int = 10
    # Load the semantic model at start-up instead of on the first analysis (used in the container).
    preload_model: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        defaults = cls()
        return cls(
            db_path=Path(os.environ.get("VENDORMATCH_DB_PATH", defaults.db_path)),
            examples_dir=Path(os.environ.get("VENDORMATCH_EXAMPLES_DIR", defaults.examples_dir)),
            max_demo_projects=int(os.environ.get("VENDORMATCH_MAX_DEMO_PROJECTS", defaults.max_demo_projects)),
            preload_model=os.environ.get("VENDORMATCH_PRELOAD_MODEL", "").lower() in ("1", "true", "yes"),
        )
