"""Strict command and path policy for test execution."""

import re
from dataclasses import dataclass

from reponyx.execution.models import ResourcePolicy


class ExecutionPolicyError(ValueError):
    """Raised when an execution request violates policy."""


@dataclass(frozen=True, slots=True)
class ApprovedCommand:
    framework: str
    argv: tuple[str, ...]


_COMMANDS: dict[str, tuple[str, ...]] = {
    "pytest": ("pytest",),
    "python_pytest": ("python", "-m", "pytest"),
    "ruff": ("ruff",),
    "python_ruff": ("python", "-m", "ruff"),
    "mypy": ("mypy",),
    "python_mypy": ("python", "-m", "mypy"),
    "npm_test": ("npm", "test"),
    "npm_run_test": ("npm", "run", "test"),
    "npm_run_lint": ("npm", "run", "lint"),
    "go_test": ("go", "test", "./..."),
    "cargo_test": ("cargo", "test"),
}
_FRAMEWORKS = {
    "pytest": "pytest",
    "python_pytest": "pytest",
    "npm_test": "npm",
    "npm_run_test": "npm",
    "go_test": "go",
    "cargo_test": "cargo",
}
_DANGEROUS = re.compile(r"[;&|<>`$]|\x00")
_FORBIDDEN_EXECUTABLES = {
    "powershell",
    "cmd",
    "bash",
    "sh",
    "curl",
    "wget",
    "ssh",
    "scp",
    "sudo",
    "chmod",
    "chown",
    "docker",
    "docker-compose",
}


def approve_command(command: str | tuple[str, ...]) -> ApprovedCommand:
    if isinstance(command, str):
        raise ExecutionPolicyError("commands must be structured argv, not shell strings")
    argv = tuple(command)
    if not argv or any(not part or _DANGEROUS.search(part) for part in argv):
        raise ExecutionPolicyError("command contains unsafe shell syntax")
    if any(".." in part or part.startswith(("/", "\\")) for part in argv):
        raise ExecutionPolicyError("command arguments cannot contain absolute or traversal paths")
    executable = argv[0].lower()
    if executable in _FORBIDDEN_EXECUTABLES or executable.endswith(
        (".exe", ".com", ".bat", ".cmd")
    ):
        raise ExecutionPolicyError("executable is not permitted")
    for identifier, allowed in _COMMANDS.items():
        if argv[: len(allowed)] == allowed:
            if identifier in {
                "pytest",
                "python_pytest",
                "ruff",
                "python_ruff",
                "mypy",
                "python_mypy",
            } and len(argv) > len(allowed):
                for argument in argv[len(allowed) :]:
                    if argument.startswith("-") or (
                        ".." not in argument and not argument.startswith(("/", "\\"))
                    ):
                        continue
                    raise ExecutionPolicyError("command argument escapes the workspace")
            return ApprovedCommand(_FRAMEWORKS.get(identifier, identifier), argv)
    raise ExecutionPolicyError("command is not in the approved execution registry")


def bounded_resources(requested: ResourcePolicy, maximum: ResourcePolicy) -> ResourcePolicy:
    if requested.timeout_seconds <= 0 or requested.timeout_seconds > maximum.timeout_seconds:
        raise ExecutionPolicyError("timeout exceeds execution policy")
    if requested.cpu_limit <= 0 or requested.cpu_limit > maximum.cpu_limit:
        raise ExecutionPolicyError("CPU limit exceeds execution policy")
    if requested.pids_limit <= 0 or requested.pids_limit > maximum.pids_limit:
        raise ExecutionPolicyError("process limit exceeds execution policy")
    if requested.output_limit <= 0 or requested.output_limit > maximum.output_limit:
        raise ExecutionPolicyError("output limit exceeds execution policy")
    return requested
