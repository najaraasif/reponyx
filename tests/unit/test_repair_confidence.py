"""Tests for repair confidence computation."""

from reponyx.repair.confidence import RepairConfidence, compute_repair_confidence
from reponyx.repair.models import RepairStatus, VerificationLevel


def test_high_confidence_completed_with_tests() -> None:
    conf = compute_repair_confidence(
        status=RepairStatus.COMPLETED,
        verification_level=VerificationLevel.FULL_TESTS_PASSED,
        iteration_count=1,
        max_iterations=5,
        evidence_count=8,
        tests_passed=10,
        tests_failed=0,
        tests_discovered=10,
        has_root_cause=True,
        has_diff=True,
        failure_analyses=[],
    )
    assert conf.level == "high"
    assert conf.score >= 0.7
    assert any("completed" in r.lower() for r in conf.reasons)
    assert any("full" in r.lower() for r in conf.reasons)


def test_medium_confidence_partial_tests() -> None:
    conf = compute_repair_confidence(
        status=RepairStatus.COMPLETED,
        verification_level=VerificationLevel.INCOMPLETE,
        iteration_count=3,
        max_iterations=5,
        evidence_count=2,
        tests_passed=2,
        tests_failed=3,
        tests_discovered=5,
        has_root_cause=False,
        has_diff=True,
        failure_analyses=[],
    )
    assert conf.level == "medium"
    assert 0.4 <= conf.score < 0.7


def test_low_confidence_failed() -> None:
    conf = compute_repair_confidence(
        status=RepairStatus.FAILED,
        verification_level=VerificationLevel.UNVERIFIED,
        iteration_count=5,
        max_iterations=5,
        evidence_count=1,
        tests_passed=0,
        tests_failed=5,
        tests_discovered=5,
        has_root_cause=False,
        has_diff=False,
        failure_analyses=[],
    )
    assert conf.level == "low"
    assert conf.score < 0.4


def test_confidence_reasons_include_all_signals() -> None:
    conf = compute_repair_confidence(
        status=RepairStatus.COMPLETED,
        verification_level=VerificationLevel.BROADER_TESTS_PASSED,
        iteration_count=3,
        max_iterations=5,
        evidence_count=6,
        tests_passed=8,
        tests_failed=0,
        tests_discovered=8,
        has_root_cause=True,
        has_diff=True,
        failure_analyses=[],
    )
    assert len(conf.reasons) >= 4
    assert any("root cause" in r.lower() for r in conf.reasons)
    assert any("evidence" in r.lower() for r in conf.reasons)


def test_confidence_score_clamped() -> None:
    conf = compute_repair_confidence(
        status=RepairStatus.COMPLETED,
        verification_level=VerificationLevel.FULL_TESTS_PASSED,
        iteration_count=1,
        max_iterations=5,
        evidence_count=20,
        tests_passed=50,
        tests_failed=0,
        tests_discovered=50,
        has_root_cause=True,
        has_diff=True,
        failure_analyses=[],
    )
    assert 0.0 <= conf.score <= 1.0


def test_patch_related_failures_reduce_confidence() -> None:
    from dataclasses import dataclass

    @dataclass(frozen=True, slots=True)
    class FakeFailure:
        is_patch_related: bool = True

    conf_no_failures = compute_repair_confidence(
        status=RepairStatus.COMPLETED,
        verification_level=VerificationLevel.TARGETED_TESTS_PASSED,
        iteration_count=2,
        max_iterations=5,
        evidence_count=3,
        tests_passed=5,
        tests_failed=2,
        tests_discovered=7,
        has_root_cause=True,
        has_diff=True,
        failure_analyses=[],
    )
    conf_with_failures = compute_repair_confidence(
        status=RepairStatus.COMPLETED,
        verification_level=VerificationLevel.TARGETED_TESTS_PASSED,
        iteration_count=2,
        max_iterations=5,
        evidence_count=3,
        tests_passed=5,
        tests_failed=2,
        tests_discovered=7,
        has_root_cause=True,
        has_diff=True,
        failure_analyses=[FakeFailure(is_patch_related=True)],
    )
    assert conf_with_failures.score < conf_no_failures.score
    assert any("patch-related" in r.lower() for r in conf_with_failures.reasons)


def test_first_iteration_bonus() -> None:
    conf_first = compute_repair_confidence(
        status=RepairStatus.COMPLETED,
        verification_level=VerificationLevel.TARGETED_TESTS_PASSED,
        iteration_count=1,
        max_iterations=5,
        evidence_count=3,
        tests_passed=5,
        tests_failed=0,
        tests_discovered=5,
        has_root_cause=True,
        has_diff=True,
        failure_analyses=[],
    )
    conf_later = compute_repair_confidence(
        status=RepairStatus.COMPLETED,
        verification_level=VerificationLevel.TARGETED_TESTS_PASSED,
        iteration_count=4,
        max_iterations=5,
        evidence_count=3,
        tests_passed=5,
        tests_failed=0,
        tests_discovered=5,
        has_root_cause=True,
        has_diff=True,
        failure_analyses=[],
    )
    assert conf_first.score > conf_later.score


def test_repair_report_includes_confidence_fields() -> None:
    from reponyx.repair.models import RepairReport

    report = RepairReport(
        repair_id="r1",
        repository_id="repo1",
        issue="test issue",
        summary="test summary",
        root_cause=None,
        files_changed=(),
        symbols_changed=(),
        patch_description=None,
        iterations=1,
        tests_run=(),
        tests_passed=(),
        tests_failed=(),
        final_status=RepairStatus.COMPLETED,
        verification_level=VerificationLevel.UNVERIFIED,
        confidence="high",
        confidence_score=0.85,
        confidence_reasons=("Root cause identified", "Tests passed"),
        patch_attempts=(),
    )
    assert report.confidence == "high"
    assert report.confidence_score == 0.85
    assert len(report.confidence_reasons) == 2
