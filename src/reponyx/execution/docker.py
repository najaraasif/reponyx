"""Docker-only execution backend with ephemeral read-only workspaces."""

import logging
import shutil
import subprocess
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

from reponyx.execution.models import ExecutionRequest, ExecutionResult, ExecutionStatus

logger = logging.getLogger(__name__)


class DockerExecutionError(RuntimeError):
    """Raised when Docker cannot create or manage an execution sandbox."""


class DockerRunner:
    def __init__(self, execution_root: str, image: str, network_disabled: bool = True) -> None:
        self.root = Path(execution_root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.image = image
        self.network_disabled = network_disabled
        import shutil

        self.docker_path = shutil.which("docker") or "docker"

    def run(self, request: ExecutionRequest, canonical_workspace: Path) -> ExecutionResult:
        started = datetime.now(UTC)
        started_clock = time.perf_counter()
        ephemeral = (self.root / request.execution_id).resolve()
        if self.root not in ephemeral.parents:
            raise DockerExecutionError("execution workspace escaped configured root")
        container_name = f"reponyx-{request.execution_id[:20]}"
        try:
            shutil.copytree(canonical_workspace, ephemeral, symlinks=True)
            requested_workdir = request.working_directory.strip()
            relative_workdir = (
                Path(requested_workdir).as_posix().lstrip("/") if requested_workdir else ""
            )
            command = [
                self.docker_path,
                "run",
                "--rm",
                "--name",
                container_name,
                "--read-only",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges:true",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,nodev,size=64m",
                "--pids-limit",
                str(request.resource_policy.pids_limit),
                "--memory",
                request.resource_policy.memory_limit,
                "--cpus",
                str(request.resource_policy.cpu_limit),
                "--mount",
                f"type=bind,source={ephemeral},target=/workspace",
                "--workdir",
                f"/workspace/{relative_workdir}" if relative_workdir else "/workspace",
            ]
            if self.network_disabled:
                command.extend(["--network", "none"])
            for key, value in request.environment_policy.allowed:
                command.extend(["--env", f"{key}={value}"])
            command.extend([self.image, *request.command])
            logger.info(
                "execution_started",
                extra={
                    "execution_id": request.execution_id,
                    "repository_id": request.repository_id,
                    "command_identifier": request.command[0],
                },
            )
            completed, stdout, stderr, output_truncated, timed_out = _run_bounded(
                command,
                request.resource_policy.timeout_seconds,
                request.resource_policy.output_limit,
                container_name,
            )
            resource_limited = completed.returncode in {137, 143}
            status = (
                ExecutionStatus.RESOURCE_LIMITED
                if resource_limited
                else ExecutionStatus.COMPLETED
                if completed.returncode == 0
                else ExecutionStatus.FAILED
            )
            if output_truncated:
                status = ExecutionStatus.RESOURCE_LIMITED
            return ExecutionResult(
                request.execution_id,
                request.repository_id,
                request.command,
                ExecutionStatus.TIMED_OUT if timed_out else status,
                completed.returncode,
                stdout,
                stderr,
                round((time.perf_counter() - started_clock) * 1000),
                timed_out,
                resource_limited or status == ExecutionStatus.RESOURCE_LIMITED,
                output_truncated,
                container_name,
                started,
                datetime.now(UTC),
                error=(
                    f"Docker process exited with code {completed.returncode}"
                    if completed.returncode == 125
                    else None
                ),
            )
        except subprocess.TimeoutExpired as exc:
            self._cleanup(container_name)
            stdout, _ = _limit_output(exc.stdout or "", request.resource_policy.output_limit)
            stderr, _ = _limit_output(exc.stderr or "", request.resource_policy.output_limit)
            return ExecutionResult(
                request.execution_id,
                request.repository_id,
                request.command,
                ExecutionStatus.TIMED_OUT,
                None,
                stdout,
                stderr,
                round((time.perf_counter() - started_clock) * 1000),
                True,
                False,
                False,
                container_name,
                started,
                datetime.now(UTC),
                error="execution timed out",
            )
        except (OSError, subprocess.SubprocessError) as exc:
            self._cleanup(container_name)
            raise DockerExecutionError("Docker execution failed") from exc
        finally:
            shutil.rmtree(ephemeral, ignore_errors=True)
            self._cleanup(container_name)

    @staticmethod
    def _cleanup(container_name: str) -> None:
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, check=False)


def _limit_output(value: str | bytes, limit: int) -> tuple[str, bool]:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    if len(value) <= limit:
        return value, False
    return value[:limit], True


def _run_bounded(
    command: list[str], timeout: float, output_limit: int, container_name: str
) -> tuple[subprocess.CompletedProcess[str], str, str, bool, bool]:
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
    )
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    output_lock = threading.Lock()
    output_exceeded = threading.Event()

    def drain(stream: TextIO, parts: list[str]) -> None:
        for chunk in iter(stream.readline, ""):
            with output_lock:
                current = sum(len(part) for part in stdout_parts + stderr_parts)
                if current < output_limit:
                    parts.append(chunk[: max(0, output_limit - current)])
                if current + len(chunk) > output_limit:
                    output_exceeded.set()
        stream.close()

    threads = [
        threading.Thread(target=drain, args=(process.stdout, stdout_parts), daemon=True),
        threading.Thread(target=drain, args=(process.stderr, stderr_parts), daemon=True),
    ]
    for thread in threads:
        thread.start()
    deadline = time.monotonic() + timeout
    timed_out = False
    while process.poll() is None:
        if output_exceeded.is_set() or time.monotonic() >= deadline:
            timed_out = not output_exceeded.is_set()
            subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, check=False)
            break
        time.sleep(0.01)
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    for thread in threads:
        thread.join(timeout=2)
    return (
        subprocess.CompletedProcess(
            command, process.returncode if process.returncode is not None else 137
        ),
        "".join(stdout_parts),
        "".join(stderr_parts),
        output_exceeded.is_set(),
        timed_out,
    )
