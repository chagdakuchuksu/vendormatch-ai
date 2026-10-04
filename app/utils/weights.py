import math
from typing import Sequence

from app.errors import InvalidWeightsError


def normalize_weights(weights: Sequence[float]) -> list[float]:
    """Scale non-negative weights so they sum to 1.

    Zero weights are allowed (the criterion is shown but contributes no points);
    an all-zero, empty, negative or non-finite set is rejected.
    """
    if not weights:
        raise InvalidWeightsError("At least one criterion is required.")
    for w in weights:
        if not math.isfinite(w) or w < 0:
            raise InvalidWeightsError(f"Weights must be finite and non-negative, got {w!r}.")
    total = math.fsum(weights)
    if total <= 0:
        raise InvalidWeightsError("At least one criterion must have a positive weight.")
    return [w / total for w in weights]
