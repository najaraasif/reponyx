"""Provider-neutral structured repair model boundary."""

from collections.abc import Sequence
from typing import Protocol

from reponyx.repair.models import ChangeType, ProposedChange, RepairState


class RepairModelError(RuntimeError):
    """Raised when a repair model cannot return a valid structured patch."""


class RepairModel(Protocol):
    def propose(
        self, issue: str, evidence: Sequence[object], state: RepairState
    ) -> tuple[list[ProposedChange], str, str, list[str]]: ...


class DeterministicRepairModel:
    """Test model with explicit proposals keyed by issue text or keywords."""

    def __init__(self, proposals: dict[str, list[ProposedChange]] | None = None) -> None:
        self.proposals = proposals or {}
        self._keyword_rules: list[tuple[list[str], list[ProposedChange]]] = []

    def add_keyword_rule(self, keywords: list[str], changes: list[ProposedChange]) -> None:
        self._keyword_rules.append((keywords, changes))

    def _match_keywords(self, issue: str) -> list[ProposedChange] | None:
        issue_lower = issue.lower()
        for keywords, changes in self._keyword_rules:
            if all(kw.lower() in issue_lower for kw in keywords):
                return changes
        return None

    def propose(
        self, issue: str, evidence: Sequence[object], state: RepairState
    ) -> tuple[list[ProposedChange], str, str, list[str]]:
        changes = self.proposals.get(issue, [])
        if not changes:
            changes = self._match_keywords(issue) or []
        if not changes:
            raise RepairModelError("deterministic repair model has no proposal for this issue")
        return (
            changes,
            "Apply the evidence-backed minimal change.",
            "The proposal targets the investigated behavior.",
            [str(item) for item in evidence[:8]],
        )


VARIANCE_FIX = ProposedChange(
    file_path="src/statistics.py",
    operation=ChangeType.MODIFIED,
    content="""\
import numpy as np
from numpy.typing import ArrayLike


def _validate_values(values: ArrayLike) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.size == 0:
        raise ValueError("Input cannot be empty")
    if not np.all(np.isfinite(array)):
        raise ValueError("Input must contain only finite values")
    return array


def mean(values: ArrayLike) -> float:
    array = _validate_values(values)
    return float(np.mean(array))


def median(values: ArrayLike) -> float:
    array = _validate_values(values)
    return float(np.median(array))


def variance(values: ArrayLike) -> float:
    array = _validate_values(values)
    return float(np.var(array))


def standard_deviation(values: ArrayLike) -> float:
    array = _validate_values(values)
    return float(np.std(array))
""",
)

CALCULATOR_FIXED = ProposedChange(
    file_path="src/calculator.py",
    operation=ChangeType.MODIFIED,
    content="""\
from typing import Sequence


def add(a: float, b: float) -> float:
    return a + b


def subtract(a: float, b: float) -> float:
    return a - b


def multiply(a: float, b: float) -> float:
    return a * b


def divide(a: float, b: float) -> float:
    if b == 0:
        raise ZeroDivisionError("Cannot divide by zero")
    return a / b


def modulo(a: float, b: float) -> float:
    if b == 0:
        raise ZeroDivisionError("Cannot modulo by zero")
    return a % b


def average(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("Cannot compute average of empty sequence")
    total = sum(values)
    return total / len(values)


def power(base: float, exponent: int) -> float:
    if exponent < 0:
        return 1.0 / power(base, -exponent)
    result = 1.0
    for _ in range(exponent):
        result *= base
    return result


def factorial(n: int) -> int:
    if n < 0:
        raise ValueError("Factorial not defined for negative numbers")
    if n == 0 or n == 1:
        return 1
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result


def is_prime(n: int) -> bool:
    if n < 2:
        return False
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0:
            return False
    return True
""",
)


CALCULATOR_BAD_FIX = ProposedChange(
    file_path="src/calculator.py",
    operation=ChangeType.MODIFIED,
    content="""\
from typing import Sequence


def add(a: float, b: float) -> float:
    return a + b


def subtract(a: float, b: float) -> float:
    return a - b


def multiply(a: float, b: float) -> float:
    return a * b


def divide(a: float, b: float) -> float:
    if b == 0:
        raise ZeroDivisionError("Cannot divide by zero")
    return a / b


def modulo(a: float, b: float) -> float:
    if b == 0:
        raise ZeroDivisionError("Cannot modulo by zero")
    return a % b


def average(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("Cannot compute average of empty sequence")
    total = sum(values)
    return total / len(values)


def power(base: float, exponent: int) -> float:
    result = 1.0
    for _ in range(exponent):
        result *= base
    return result


def factorial(n: int) -> int:
    if n < 0:
        raise ValueError("Factorial not defined for negative numbers")
    if n == 0 or n == 1:
        return 1
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result


def is_prime(n: int) -> bool:
    if n < 3:
        return True
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0:
            return False
    return True
""",
)


def build_default_deterministic_model() -> DeterministicRepairModel:
    model = DeterministicRepairModel()
    model.add_keyword_rule(
        keywords=["average", "broken"],
        changes=[CALCULATOR_BAD_FIX],
    )
    model.add_keyword_rule(
        keywords=["variance", "population"],
        changes=[VARIANCE_FIX],
    )
    model.add_keyword_rule(
        keywords=["average"],
        changes=[CALCULATOR_FIXED],
    )
    model.add_keyword_rule(
        keywords=["integer division"],
        changes=[CALCULATOR_FIXED],
    )
    model.add_keyword_rule(
        keywords=["power"],
        changes=[CALCULATOR_FIXED],
    )
    model.add_keyword_rule(
        keywords=["exponent"],
        changes=[CALCULATOR_FIXED],
    )
    model.add_keyword_rule(
        keywords=["division", "zero"],
        changes=[CALCULATOR_FIXED],
    )
    model.add_keyword_rule(
        keywords=["divide"],
        changes=[CALCULATOR_FIXED],
    )
    model.add_keyword_rule(
        keywords=["prime"],
        changes=[CALCULATOR_FIXED],
    )
    model.add_keyword_rule(
        keywords=["modulo"],
        changes=[CALCULATOR_FIXED],
    )
    model.add_keyword_rule(
        keywords=["factorial"],
        changes=[CALCULATOR_FIXED],
    )
    model.add_keyword_rule(
        keywords=["average", "broken"],
        changes=[CALCULATOR_BAD_FIX],
    )
    return model
