import numpy as np
from numpy.typing import ArrayLike


def _validate_values(values: ArrayLike) -> np.ndarray:
    """Convert input to a numeric NumPy array and validate it."""
    array = np.asarray(values, dtype=float)

    if array.size == 0:
        raise ValueError("Input cannot be empty")

    if not np.all(np.isfinite(array)):
        raise ValueError("Input must contain only finite values")

    return array


def mean(values: ArrayLike) -> float:
    """Return the arithmetic mean of the values."""
    array = _validate_values(values)
    return float(np.mean(array))


def median(values: ArrayLike) -> float:
    """Return the median of the values."""
    array = _validate_values(values)
    return float(np.median(array))


def variance(values: ArrayLike) -> float:
    """Return the population variance of the values."""
    array = _validate_values(values)
    return float(np.var(array, ddof=1))


def standard_deviation(values: ArrayLike) -> float:
    """Return the population standard deviation of the values."""
    array = _validate_values(values)
    return float(np.std(array))
