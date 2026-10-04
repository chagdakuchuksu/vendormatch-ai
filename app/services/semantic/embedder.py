"""Text embedding behind a small interface so scoring never depends on a concrete model.

Production uses Sentence Transformers with all-MiniLM-L6-v2, running locally. The model
weights are downloaded once from the Hugging Face Hub (or baked into the Docker image);
no project or vendor text ever leaves the machine.
"""

import threading
from typing import Protocol, Sequence

from app.config import DEFAULT_SCORING_CONFIG
from app.errors import SemanticModelUnavailableError

DEFAULT_MODEL_NAME = DEFAULT_SCORING_CONFIG.semantic_model_name


class Embedder(Protocol):
    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one embedding vector per input text, in order."""
        ...


class SentenceTransformerEmbedder:
    """Lazy-loading, caching wrapper around a SentenceTransformer model."""

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME, device: str = "cpu", cache_size: int = 10_000):
        self.model_name = model_name
        self.device = device
        self.cache_size = cache_size
        self._model = None
        self._cache: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _load(self):
        with self._lock:
            if self._model is None:
                try:
                    # Imported lazily so the rest of the app (and unit tests) never need torch.
                    from sentence_transformers import SentenceTransformer

                    self._model = SentenceTransformer(self.model_name, device=self.device)
                except Exception as exc:
                    raise SemanticModelUnavailableError(
                        f"The local semantic model '{self.model_name}' could not be loaded.",
                        {"reason": str(exc)},
                    ) from exc
        return self._model

    def warm_up(self) -> None:
        """Load the model and run one tiny inference so the first real request is fast."""
        self.encode(["warm-up"])

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        missing = list(dict.fromkeys(t for t in texts if t not in self._cache))
        if missing:
            vectors = self._load().encode(missing, normalize_embeddings=True, convert_to_numpy=True)
            with self._lock:
                if len(self._cache) + len(missing) > self.cache_size:
                    self._cache.clear()
                for text, vector in zip(missing, vectors):
                    self._cache[text] = vector.tolist()
        return [self._cache[t] for t in texts]
