"""Deterministic stand-ins for the sentence-transformers embedder (no torch, no download)."""

import math
import re
import zlib
from typing import Sequence


def unit_vector_with_cosine(c: float) -> list[float]:
    """2-D unit vector whose cosine with [1, 0] is exactly `c`."""
    return [c, math.sqrt(max(0.0, 1 - c * c))]


class TableEmbedder:
    """Returns predefined vectors; lets a test dictate exact cosine similarities.

    Unknown texts raise KeyError so a test fails loudly if unexpected text is embedded.
    """

    def __init__(self, table: dict[str, Sequence[float]]):
        self.table = table
        self.calls: list[list[str]] = []

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [list(self.table[t]) for t in texts]


class BagOfWordsEmbedder:
    """Hashed bag-of-words vectors: texts sharing words are similar. Deterministic across runs."""

    STOPWORDS = {"a", "an", "and", "the", "of", "for", "to", "in", "on", "we", "our", "with", "is", "are", "have"}

    def __init__(self, dims: int = 256):
        self.dims = dims
        self.calls: list[list[str]] = []

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        out = []
        for text in texts:
            vec = [0.0] * self.dims
            for word in re.findall(r"[a-z0-9]+", text.lower()):
                if word not in self.STOPWORDS:
                    vec[zlib.crc32(word.encode()) % self.dims] += 1.0
            out.append(vec)
        return out


class ConstantSimilarityEmbedder:
    """Every text after the first in a call gets the same cosine with the first one."""

    def __init__(self, similarity: float):
        self.similarity = similarity
        self.calls: list[list[str]] = []

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [[1.0, 0.0]] + [unit_vector_with_cosine(self.similarity) for _ in texts[1:]]
