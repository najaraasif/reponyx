import pytest

from reponyx.execution.models import ResourcePolicy
from reponyx.execution.policy import ExecutionPolicyError, approve_command, bounded_resources
from reponyx.execution.tests import approved_test_command, parse_test_output


def test_supported_commands_are_structured() -> None:
    approved = approved_test_command("pytest")

    assert approved.framework == "pytest"
    assert approved.argv == ("python", "-m", "pytest", "-q")


@pytest.mark.parametrize(
    "command",
    [
        ("pytest;", "bad"),
        ("pytest", "&&", "bad"),
        ("pytest", "|", "bad"),
        ("pytest", "$(bad)"),
        ("pytest", "`bad`"),
        ("pytest", "../../outside"),
        ("sh", "-c", "echo bad"),
        ("docker", "ps"),
        ("git", "push"),
    ],
)
def test_unsafe_commands_are_rejected(command: tuple[str, ...]) -> None:
    with pytest.raises(ExecutionPolicyError):
        approve_command(command)


def test_command_strings_are_never_treated_as_shell_input() -> None:
    with pytest.raises(ExecutionPolicyError):
        approve_command("pytest && echo unsafe")


def test_resource_policy_is_bounded() -> None:
    maximum = ResourcePolicy(30, "512m", 1.0, 64, 1_000)

    assert (
        bounded_resources(ResourcePolicy(10, "512m", 1.0, 64, 500), maximum).timeout_seconds == 10
    )
    with pytest.raises(ExecutionPolicyError):
        bounded_resources(ResourcePolicy(31, "512m", 1.0, 64, 500), maximum)


def test_pytest_output_is_normalized() -> None:
    summary = parse_test_output("pytest", "3 passed, 1 failed, 2 skipped in 0.12s", "", 120)

    assert summary.passed == 3
    assert summary.failed == 1
    assert summary.skipped == 2
    assert summary.parsing_complete
