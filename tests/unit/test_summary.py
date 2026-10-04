"""Neutral labels, summaries, score explanations and point accounting."""

import dataclasses

import pytest

from app.config import DEFAULT_SCORING_CONFIG as CFG
from app.services.criteria_builder import build_criteria
from app.services.scoring.engine import evaluate_vendor
from app.services.scoring.summary import compatibility_label
from tests.helpers import FixedSemanticScorer, spec_example_project, vendor

TECHS = ["React Native", "Node.js", "PostgreSQL"]
FORBIDDEN = ("choose", "recommend", "best", "winner", "select", "hire", "should")


def evaluate(semantic=1.0, **v):
    p = spec_example_project()
    return evaluate_vendor(p, build_criteria(p), vendor(**v), semantic_scorer=FixedSemanticScorer(semantic))


@pytest.mark.parametrize(
    ("score", "hard_met", "label"),
    [
        (100, True, "Strong compatibility"),
        (85, True, "Strong compatibility"),
        (84.9, True, "Mostly compatible with some concerns"),
        (65, True, "Mostly compatible with some concerns"),
        (64.9, True, "Requires review"),
        (0, True, "Requires review"),
        (99, False, "Hard requirement failed"),
    ],
)
def test_compatibility_label_thresholds(score, hard_met, label):
    assert compatibility_label(score, hard_met, CFG) == label


def test_label_thresholds_come_from_config():
    cfg = dataclasses.replace(CFG, label_strong_min=99, label_mostly_min=10)
    assert compatibility_label(98, True, cfg) == "Mostly compatible with some concerns"


def test_points_add_up():
    a = evaluate(proposed_budget=55_000, proposed_duration=8, years_experience=4, technologies=TECHS)
    assert sum(r.contribution for r in a.criteria) == pytest.approx(a.base_score, abs=0.05)
    assert sum(r.max_points for r in a.criteria) == pytest.approx(100)
    for r in a.criteria:
        assert r.contribution + r.points_lost == pytest.approx(r.max_points)
    assert a.penalty_points == pytest.approx(a.base_score - a.overall_score, abs=0.1)


def test_score_explanation_with_penalty():
    a = evaluate(proposed_budget=40_000, proposed_duration=8, years_experience=10, technologies=TECHS)
    assert a.score_explanation == (
        "Base score 83.33 (sum of weighted criterion scores) × hard-fail multiplier 0.5 (Duration ×0.5) = 41.67, shown as 41.7."
    )


def test_score_explanation_without_penalty():
    a = evaluate(proposed_budget=55_000, proposed_duration=5, years_experience=8, technologies=TECHS)
    assert a.score_explanation == (
        "Base score 98.00 (sum of weighted criterion scores); no hard requirement failed, so the overall score is 98.0."
    )


def test_summary_for_hard_failure():
    a = evaluate(proposed_budget=40_000, proposed_duration=8, years_experience=10, technologies=TECHS)
    assert a.compatibility_label == "Hard requirement failed"
    assert a.summary == (
        "Hard requirement failed: Duration (2 months over the strict deadline). The overall score is multiplied "
        "by 0.5; the vendor remains in the comparison for review."
    )


def test_summary_for_compatible_vendor_lists_gaps():
    a = evaluate(semantic=0.5, proposed_budget=55_000, proposed_duration=5, years_experience=8, technologies=["React Native", "Node.js", "MySQL"])
    assert a.summary.startswith("Hard requirement failed")  # PostgreSQL is an auto Critical + Hard requirement
    b = evaluate(semantic=0.5, proposed_budget=55_000, proposed_duration=5, years_experience=4, technologies=TECHS)
    assert b.summary == (
        f"{b.compatibility_label}: meets all 4 hard requirements; partially met: Budget, E-commerce experience, Company experience."
    )
    c = evaluate(semantic=0.0, proposed_budget=55_000, proposed_duration=5, years_experience=3, technologies=TECHS)
    assert c.summary == (
        f"{c.compatibility_label}: meets all 4 hard requirements; not met: E-commerce experience, Company experience; "
        "partially met: Budget."
    )


def test_major_concerns_order():
    a = evaluate(semantic=0.0, proposed_budget=55_000, proposed_duration=8, years_experience=4, technologies=TECHS)
    assert a.major_concerns[0] == "Duration: 2 months over the strict deadline (hard requirement)"
    assert a.major_concerns[1] == "E-commerce experience: fixed"  # unmet soft criterion
    assert a.major_concerns[2:] == ["Budget: €5,000 over budget", "Company experience: 1 year below the minimum"]


@pytest.mark.parametrize("duration", [5, 8])
@pytest.mark.parametrize("budget", [20_000, 50_000, 60_000])
def test_vendor_texts_are_neutral(duration, budget):
    a = evaluate(proposed_budget=budget, proposed_duration=duration, years_experience=6, technologies=TECHS)
    texts = [a.summary, a.compatibility_label, a.status_label, a.score_explanation, *a.major_concerns]
    for text in texts:
        assert not any(word in text.lower() for word in FORBIDDEN), text
