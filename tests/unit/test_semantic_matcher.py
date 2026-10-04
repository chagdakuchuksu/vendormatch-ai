import pytest

from app.schemas.enums import CriterionKind
from app.services.semantic.matcher import (
    EvidenceChunk,
    best_match,
    cosine_similarity,
    evidence_chunks,
    requirement_text,
    similarity_to_score,
    split_sentences,
)
from tests.fakes import BagOfWordsEmbedder, TableEmbedder
from tests.helpers import criterion, vendor

L, U = 0.30, 0.60


# --- sentence splitting ---------------------------------------------------------------------

def test_split_basic_sentences():
    assert split_sentences("We build apps. We test them! Do we ship? Yes.") == [
        "We build apps.", "We test them!", "Do we ship?", "Yes.",
    ]


def test_split_keeps_abbreviations_and_dotted_names():
    text = "We use Node.js and React Native, e.g. for retail apps. Support is incl. in the price."
    assert split_sentences(text) == [
        "We use Node.js and React Native, e.g. for retail apps.",
        "Support is incl. in the price.",
    ]


def test_split_newlines_and_bullets():
    text = "Highlights:\n- Built six online shops\n* Integrated Stripe\n1. GDPR audits\n\n"
    assert split_sentences(text) == ["Highlights:", "Built six online shops", "Integrated Stripe", "GDPR audits"]


@pytest.mark.parametrize("text", ["", "   ", "\n\n", "- \n ... \n 42."])
def test_split_empty_or_non_textual(text):
    assert split_sentences(text) == []


def test_evidence_chunks_label_sources():
    v = vendor(proposal_text="First claim. Second claim.", previous_projects=["Shop for a florist.", "Bank app. Many users."])
    assert evidence_chunks(v) == [
        EvidenceChunk("First claim.", "proposal"),
        EvidenceChunk("Second claim.", "proposal"),
        EvidenceChunk("Shop for a florist.", "previous project 1"),
        EvidenceChunk("Bank app.", "previous project 2"),
        EvidenceChunk("Many users.", "previous project 2"),
    ]


def test_requirement_text_is_the_description():
    c = criterion(CriterionKind.TEXT, name="E-commerce", description="  Previous e-commerce experience ")
    assert requirement_text(c) == "Previous e-commerce experience"


# --- cosine & best match --------------------------------------------------------------------

@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [([1, 0], [1, 0], 1.0), ([1, 0], [0, 1], 0.0), ([1, 0], [-1, 0], -1.0), ([3, 4], [6, 8], 1.0), ([0, 0], [1, 0], 0.0)],
)
def test_cosine_similarity(a, b, expected):
    assert cosine_similarity(a, b) == pytest.approx(expected)


def test_best_match_picks_most_similar_chunk():
    chunks = [EvidenceChunk("Our office has plants.", "proposal"), EvidenceChunk("We built online retail shops.", "proposal")]
    m = best_match("online retail experience", chunks, BagOfWordsEmbedder())
    assert m.chunk.text == "We built online retail shops."
    assert m.requirement_text == "online retail experience"


def test_best_match_tie_goes_to_first_chunk():
    emb = TableEmbedder({"req": [1, 0], "a": [1, 1], "b": [1, 1]})
    m = best_match("req", [EvidenceChunk("a", "proposal"), EvidenceChunk("b", "proposal")], emb)
    assert m.chunk.text == "a"


def test_best_match_embeds_in_one_batch():
    emb = BagOfWordsEmbedder()
    best_match("x", [EvidenceChunk("a b", "proposal"), EvidenceChunk("c d", "proposal")], emb)
    assert emb.calls == [["x", "a b", "c d"]]


def test_best_match_requires_chunks():
    with pytest.raises(ValueError):
        best_match("x", [], BagOfWordsEmbedder())


# --- threshold ramp -------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("sim", "score", "strength"),
    [
        (-0.5, 0.0, "none"),
        (0.0, 0.0, "none"),
        (0.2999, 0.0, "none"),
        (0.30, 0.0, "none"),
        (0.36, 0.2, "partial"),
        (0.45, 0.5, "partial"),
        (0.5999, pytest.approx(0.99967, abs=1e-4), "partial"),
        (0.60, 1.0, "strong"),
        (0.95, 1.0, "strong"),
    ],
)
def test_similarity_to_score(sim, score, strength):
    s, st = similarity_to_score(sim, L, U)
    assert s == pytest.approx(score) and st == strength


def test_ramp_is_monotonic_and_bounded():
    sims = [i / 1000 for i in range(-1000, 1001)]
    scores = [similarity_to_score(s, L, U)[0] for s in sims]
    assert all(0.0 <= s <= 1.0 for s in scores)
    assert all(b >= a for a, b in zip(scores, scores[1:]))


@pytest.mark.parametrize(("lower", "upper"), [(0.6, 0.3), (0.5, 0.5)])
def test_invalid_thresholds_rejected(lower, upper):
    with pytest.raises(ValueError):
        similarity_to_score(0.4, lower, upper)
