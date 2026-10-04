import math

import pytest

from app.errors import InvalidWeightsError
from app.utils.weights import normalize_weights


def test_weights_sum_to_one():
    assert normalize_weights([4, 3, 2, 1]) == pytest.approx([0.4, 0.3, 0.2, 0.1])


def test_scale_invariant():
    assert normalize_weights([40, 30, 30]) == pytest.approx(normalize_weights([4, 3, 3]))


def test_zero_weight_allowed_and_contributes_nothing():
    assert normalize_weights([0, 2, 2]) == pytest.approx([0.0, 0.5, 0.5])


def test_single_weight():
    assert normalize_weights([7]) == [1.0]


@pytest.mark.parametrize("weights", [[0, 0], [0.0]])
def test_all_zero_weights_rejected(weights):
    with pytest.raises(InvalidWeightsError, match="positive weight"):
        normalize_weights(weights)


def test_empty_rejected():
    with pytest.raises(InvalidWeightsError):
        normalize_weights([])


@pytest.mark.parametrize("bad", [-1, math.nan, math.inf])
def test_negative_or_non_finite_rejected(bad):
    with pytest.raises(InvalidWeightsError):
        normalize_weights([1, bad])
