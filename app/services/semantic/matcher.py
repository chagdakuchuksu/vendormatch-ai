"""Sentence-level semantic matching: pure functions on top of an Embedder."""

import math
import re
from dataclasses import dataclass
from typing import Literal, Sequence

from app.schemas.criterion import Criterion
from app.schemas.vendor import VendorCreate
from app.services.semantic.embedder import Embedder

Strength = Literal["strong", "partial", "none"]

# A "." after one of these does not end a sentence.
_ABBREVIATIONS = {"e.g.", "i.e.", "etc.", "approx.", "incl.", "vs.", "ca.", "no.", "dr.", "mr.", "ms."}
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")


@dataclass(frozen=True)
class EvidenceChunk:
    text: str
    source: str  # "proposal" or "previous project 2"


@dataclass(frozen=True)
class SemanticMatch:
    requirement_text: str
    chunk: EvidenceChunk
    similarity: float


def split_sentences(text: str) -> list[str]:
    """Split prose into sentences; newlines and bullet points also separate items."""
    sentences: list[str] = []
    for line in text.splitlines():
        line = _BULLET.sub("", line).strip()
        if not line:
            continue
        buffer = ""
        for part in _SENTENCE_END.split(line):
            buffer = f"{buffer} {part}" if buffer else part
            last_word = buffer.rsplit(" ", 1)[-1].lower()
            if last_word not in _ABBREVIATIONS:
                sentences.append(buffer.strip())
                buffer = ""
        if buffer:
            sentences.append(buffer.strip())
    return [s for s in sentences if any(ch.isalpha() for ch in s)]


def evidence_chunks(vendor: VendorCreate) -> list[EvidenceChunk]:
    chunks = [EvidenceChunk(s, "proposal") for s in split_sentences(vendor.proposal_text)]
    for i, project in enumerate(vendor.previous_projects, start=1):
        chunks += [EvidenceChunk(s, f"previous project {i}") for s in split_sentences(project)]
    return chunks


def requirement_text(criterion: Criterion) -> str:
    """The user's requirement statement (the description; the name is only a label)."""
    return (criterion.description or criterion.name).strip()


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    dot = math.fsum(x * y for x, y in zip(a, b))
    norm = math.sqrt(math.fsum(x * x for x in a)) * math.sqrt(math.fsum(y * y for y in b))
    return dot / norm if norm else 0.0


def best_match(requirement: str, chunks: Sequence[EvidenceChunk], embedder: Embedder) -> SemanticMatch:
    """Highest-similarity chunk; ties go to the earliest chunk so results are deterministic."""
    if not chunks:
        raise ValueError("no evidence chunks to match against")
    vectors = embedder.encode([requirement, *(c.text for c in chunks)])
    req_vec, chunk_vecs = vectors[0], vectors[1:]
    sims = [cosine_similarity(req_vec, v) for v in chunk_vecs]
    best = max(range(len(chunks)), key=lambda i: (sims[i], -i))
    return SemanticMatch(requirement, chunks[best], sims[best])


def similarity_to_score(similarity: float, lower: float, upper: float) -> tuple[float, Strength]:
    """Linear ramp: <= lower -> 0 ("none"), >= upper -> 1 ("strong"), in between "partial"."""
    if not lower < upper:
        raise ValueError("lower threshold must be below upper threshold")
    if similarity >= upper:
        return 1.0, "strong"
    if similarity <= lower:
        return 0.0, "none"
    return (similarity - lower) / (upper - lower), "partial"
