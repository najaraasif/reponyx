"""Approved test-command registry and normalized output parsers."""

import re
from collections.abc import Callable

from reponyx.execution.models import TestSummary
from reponyx.execution.policy import ApprovedCommand, ExecutionPolicyError, approve_command

TEST_COMMANDS: dict[str, tuple[str, ...]] = {
    "pytest": ("python", "-m", "pytest", "-q"),
    "npm": ("npm", "test"),
    "go": ("go", "test", "./..."),
    "cargo": ("cargo", "test"),
}


def approved_test_command(framework: str) -> ApprovedCommand:
    command = TEST_COMMANDS.get(framework.lower())
    if command is None:
        raise ExecutionPolicyError("test framework is not supported")
    return approve_command(command)


def parse_test_output(framework: str, stdout: str, stderr: str, duration_ms: int) -> TestSummary:
    parser: Callable[[str, str, int], TestSummary] = {
        "pytest": _parse_pytest,
        "npm": _parse_npm,
        "go": _parse_go,
        "cargo": _parse_cargo,
    }.get(framework, _parse_unknown)
    return parser(stdout, stderr, duration_ms)


def _parse_pytest(stdout: str, stderr: str, duration_ms: int) -> TestSummary:
    text = f"{stdout}\n{stderr}"
    match = re.search(r"(?:(\d+) passed)?[ ,]*(?:(\d+) failed)?[ ,]*(?:(\d+) skipped)?", text)
    if not match or not any(match.groups()):
        return TestSummary(
            "pytest",
            duration_ms=duration_ms,
            parsing_complete=False,
            failure_summaries=(stderr[-2_000:],) if stderr else (),
        )
    passed, failed, skipped = (int(value or 0) for value in match.groups())
    return TestSummary(
        "pytest", passed, failed, skipped, passed + failed + skipped, duration_ms, True, ()
    )


def _parse_npm(stdout: str, stderr: str, duration_ms: int) -> TestSummary:
    text = f"{stdout}\n{stderr}"
    failed = 1 if re.search(r"(FAIL|failed|npm ERR!)", text, re.IGNORECASE) else 0
    passed = 0 if failed else 1
    return TestSummary(
        "npm",
        passed,
        failed,
        0,
        passed + failed,
        duration_ms,
        False,
        (stderr[-2_000:],) if failed and stderr else (),
    )


def _parse_go(stdout: str, stderr: str, duration_ms: int) -> TestSummary:
    passed = len(re.findall(r"--- PASS:", stdout))
    failed = len(re.findall(r"--- FAIL:", stdout))
    return TestSummary("go", passed, failed, 0, passed + failed, duration_ms, True, ())


def _parse_cargo(stdout: str, stderr: str, duration_ms: int) -> TestSummary:
    match = re.search(r"(\d+) passed; (\d+) failed; (\d+) ignored", stdout)
    if not match:
        return TestSummary("cargo", duration_ms=duration_ms, parsing_complete=False)
    passed, failed, skipped = (int(value) for value in match.groups())
    return TestSummary(
        "cargo", passed, failed, skipped, passed + failed + skipped, duration_ms, True, ()
    )


def _parse_unknown(stdout: str, stderr: str, duration_ms: int) -> TestSummary:
    return TestSummary("unknown", duration_ms=duration_ms, parsing_complete=False)
