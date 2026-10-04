import pytest

from app.config import DEFAULT_SCORING_CONFIG as CFG
from app.schemas.enums import CriterionKind, CriterionStatus
from app.services.scoring.technology import score_technology
from app.utils.text import normalize_technology
from tests.helpers import criterion, vendor

TECH = CriterionKind.TECHNOLOGY


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("React Native", "react-native"),
        ("React Native", "ReactNative"),
        ("Node.js", "node"),
        ("Node.js", "NodeJS"),
        ("PostgreSQL", "Postgres"),
        ("C#", "c sharp"),
        ("TypeScript", "TS"),
    ],
)
def test_normalization_equivalences(a, b):
    assert normalize_technology(a) == normalize_technology(b)


@pytest.mark.parametrize(("a", "b"), [("React", "React Native"), ("Java", "JavaScript"), ("C", "C++")])
def test_normalization_keeps_distinct_technologies_apart(a, b):
    assert normalize_technology(a) != normalize_technology(b)


def test_listed_technology_passes():
    c = criterion(TECH, technology="React Native", requirement_type="hard", importance="critical")
    r = score_technology(c, vendor(technologies=["react-native", "Node.js"]), CFG)
    assert (r.score, r.status, r.hard_failure) == (1.0, CriterionStatus.PASS, False)
    assert r.vendor_value == "react-native"


def test_unlisted_hard_technology_fails_with_penalty():
    c = criterion(TECH, technology="React Native", requirement_type="hard", importance="critical")
    r = score_technology(c, vendor(technologies=["Flutter", "Node.js"]), CFG)
    assert (r.score, r.status) == (0.0, CriterionStatus.FAIL)
    assert r.hard_failure and r.penalty_factor == 0.5
    assert "Flutter, Node.js" in r.explanation


def test_unlisted_soft_technology_fails_without_penalty():
    c = criterion(TECH, technology="PostgreSQL", requirement_type="soft")
    r = score_technology(c, vendor(technologies=["MySQL"]), CFG)
    assert r.status == CriterionStatus.FAIL
    assert not r.hard_failure and r.penalty_factor is None


def test_no_technologies_listed_is_missing():
    c = criterion(TECH, technology="PostgreSQL", requirement_type="hard")
    r = score_technology(c, vendor(technologies=[]), CFG)
    assert r.status == CriterionStatus.MISSING
    assert r.hard_failure


def test_technology_is_not_inferred_from_proposal_text():
    """Technology matching is deterministic: mentioning it in prose is not enough."""
    c = criterion(TECH, technology="React Native")
    r = score_technology(c, vendor(technologies=["Flutter"], proposal_text="We love React Native."), CFG)
    assert r.status == CriterionStatus.FAIL
