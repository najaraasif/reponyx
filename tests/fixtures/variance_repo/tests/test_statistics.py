import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from statistics import variance


def test_variance_population():
    """Population variance of [1,2,3,4,5] is 2.0."""
    assert variance([1, 2, 3, 4, 5]) == pytest.approx(2.0)


def test_variance_single_value():
    """Population variance of a single value is 0.0."""
    assert variance([5.0]) == pytest.approx(0.0)


def test_variance_two_values():
    """Population variance of [1,3] is 1.0."""
    assert variance([1, 3]) == pytest.approx(1.0)
