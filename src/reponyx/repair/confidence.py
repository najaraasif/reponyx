"""Structured confidence computation for repair reports."""

from __future__ import annotations

from dataclasses import dataclass

from reponyx.repair.models import RepairStatus, VerificationLevel


@dataclass(frozen=True, slots=True)
class RepairConfidence:
    level: str
    score: float
    reasons: tuple[str, ...]


def compute_repair_confidence(
    status: RepairStatus,
    verification_level: VerificationLevel,
    iteration_count: int,
    max_iterations: int,
    evidence_count: int,
    tests_passed: int,
    tests_failed: int,
    tests_discovered: int,
    has_root_cause: bool,
    has_diff: bool,
    failure_analyses: list[object],
) -> RepairConfidence:
    score = 0.0
    reasons: list[str] = []

    if status == RepairStatus.COMPLETED:
        score += 0.3
        reasons.append("Repair completed successfully")
    elif status == RepairStatus.FAILED:
        score += 0.0
        reasons.append("Repair failed")
    else:
        score += 0.1
        reasons.append(f"Repair status: {status.value}")

    if verification_level == VerificationLevel.FULL_TESTS_PASSED:
        score += 0.3
        reasons.append("Full test suite passed")
    elif verification_level == VerificationLevel.BROADER_TESTS_PASSED:
        score += 0.2
        reasons.append("Broader tests passed")
    elif verification_level == VerificationLevel.TARGETED_TESTS_PASSED:
        score += 0.15
        reasons.append("Targeted tests passed")
    elif verification_level == VerificationLevel.INCOMPLETE:
        score += 0.05
        reasons.append("Verification incomplete")
    else:
        reasons.append("No tests verified")

    if has_root_cause:
        score += 0.15
        reasons.append("Root cause identified")

    if evidence_count >= 5:
        score += 0.1
        reasons.append(f"{evidence_count} evidence items found")
    elif evidence_count >= 2:
        score += 0.05
        reasons.append(f"{evidence_count} evidence items found")
    elif evidence_count > 0:
        reasons.append(f"Only {evidence_count} evidence item found")

    if tests_passed > 0 and tests_failed == 0:
        score += 0.1
        reasons.append(f"All {tests_passed} tests passed")
    elif tests_passed > 0:
        score += 0.05
        reasons.append(f"{tests_passed} passed, {tests_failed} failed")
    elif tests_discovered > 0:
        reasons.append(f"{tests_discovered} tests discovered but none passed")

    if iteration_count <= 1:
        score += 0.05
        reasons.append("Resolved in first iteration")
    elif iteration_count <= 3:
        reasons.append(f"Resolved in {iteration_count} iterations")
    else:
        score -= 0.05
        reasons.append(f"Took {iteration_count} iterations")

    if has_diff:
        score += 0.05
        reasons.append("Patch diff generated")

    patch_related_failures = sum(
        1 for fa in failure_analyses
        if getattr(fa, "is_patch_related", False)
    )
    if patch_related_failures > 0:
        score -= 0.1 * patch_related_failures
        reasons.append(f"{patch_related_failures} patch-related failures detected")

    score = max(0.0, min(1.0, score))

    if score >= 0.7:
        level = "high"
    elif score >= 0.4:
        level = "medium"
    else:
        level = "low"

    return RepairConfidence(
        level=level,
        score=round(score, 2),
        reasons=tuple(reasons),
    )
