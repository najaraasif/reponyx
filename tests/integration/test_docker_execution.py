import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from reponyx.execution.docker import DockerRunner
from reponyx.execution.models import EnvironmentPolicy, ExecutionRequest, ResourcePolicy

pytestmark = pytest.mark.integration


def test_docker_is_available_for_sandbox_integration() -> None:
    if shutil.which("docker") is None:
        pytest.skip("Docker is unavailable")

    result = __import__("subprocess").run(
        ["docker", "info"], capture_output=True, check=False, text=True
    )
    if result.returncode != 0:
        pytest.skip("Docker daemon is unavailable")

    assert DockerRunner is not None


def test_docker_sandbox_executes_approved_fixture_without_network(tmp_path: Path) -> None:
    if shutil.which("docker") is None:
        pytest.skip("Docker is unavailable")
    info = __import__("subprocess").run(["docker", "info"], capture_output=True, check=False)
    if info.returncode != 0:
        pytest.skip("Docker daemon is unavailable")
    image = "reponyx-executor:phase4"
    if (
        __import__("subprocess")
        .run(["docker", "image", "inspect", image], capture_output=True, check=False)
        .returncode
        != 0
    ):
        pytest.skip("execution image is not built")

    runner = DockerRunner(str(tmp_path / "executions"), image)
    source = tmp_path / "workspace"
    source.mkdir()
    (source / "test_sample.py").write_text("def test_ok():\n    assert True\n")
    request = ExecutionRequest(
        "integration-execution",
        "repo",
        ("python", "-m", "pytest", "-q"),
        "",
        30,
        EnvironmentPolicy(()),
        ResourcePolicy(30, "256m", 1.0, 32, 10_000),
    )

    result = runner.run(request, source)

    assert result.status.value == "completed"
    assert result.exit_code == 0
    assert not (tmp_path / "executions" / "integration-execution").exists()


def _docker_ready() -> bool:
    return (
        shutil.which("docker") is not None
        and subprocess.run(["docker", "info"], capture_output=True, check=False).returncode == 0
    )


def _image_ready() -> bool:
    return (
        subprocess.run(
            ["docker", "image", "inspect", "reponyx-executor:phase4"],
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def test_sandbox_security_matrix(tmp_path: Path) -> None:
    if not _docker_ready():
        pytest.skip("Docker daemon is unavailable")
    if not _image_ready():
        pytest.skip("execution image is not built")
    runner = DockerRunner(str(tmp_path / "executions"), "reponyx-executor:phase4")
    source = tmp_path / "workspace"
    source.mkdir()
    (source / "test_security.py").write_text(
        "import os\n"
        "import pathlib\n"
        "import socket\n"
        "def test_security():\n"
        "    try:\n"
        "        pathlib.Path('attempted-write.txt').write_text('blocked')\n"
        "    except OSError:\n"
        "        pass\n"
        "    else:\n"
        "        assert False, 'read-only mount unexpectedly writable'\n"
        "    assert not os.environ.get('OPENAI_API_KEY')\n"
        "    assert not os.environ.get('GITHUB_TOKEN')\n"
        "    assert not os.environ.get('DATABASE_URL')\n"
        "    try:\n"
        "        socket.create_connection(('example.com', 80), timeout=1)\n"
        "    except OSError:\n"
        "        return\n"
        "    assert False, 'network unexpectedly available'\n"
    )
    request = ExecutionRequest(
        "security-matrix",
        "repo-security",
        ("python", "-m", "pytest", "-q"),
        "",
        30,
        EnvironmentPolicy((("reponyx_TEST_SENTINEL", "present"),)),
        ResourcePolicy(30, "256m", 1.0, 32, 10_000),
    )

    result = runner.run(request, source)

    assert result.status.value == "completed"
    assert result.exit_code == 0
    assert not (source / "attempted-write.txt").exists()
    assert not (tmp_path / "executions" / "security-matrix").exists()
    assert (
        subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                "name=reponyx-security-matrix",
                "--format",
                "{{.ID}}",
            ],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        == ""
    )


def test_timeout_removes_container_and_workspace(tmp_path: Path) -> None:
    if not _docker_ready() or not _image_ready():
        pytest.skip("Docker image or daemon is unavailable")
    runner = DockerRunner(str(tmp_path / "executions"), "reponyx-executor:phase4")
    source = tmp_path / "workspace"
    source.mkdir()
    (source / "test_timeout.py").write_text(
        "import time\ndef test_timeout():\n    time.sleep(30)\n"
    )
    request = ExecutionRequest(
        "timeout-matrix",
        "repo-timeout",
        ("python", "-m", "pytest", "-q"),
        "",
        2,
        EnvironmentPolicy(()),
        ResourcePolicy(2, "256m", 1.0, 32, 10_000),
    )

    result = runner.run(request, source)

    assert result.timed_out
    assert result.status.value == "timed_out"
    assert not (tmp_path / "executions" / "timeout-matrix").exists()
    time.sleep(0.5)
    assert (
        subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                "name=reponyx-timeout-matrix",
                "--format",
                "{{.ID}}",
            ],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        == ""
    )


def _runner(tmp_path: Path) -> DockerRunner:
    if not _docker_ready() or not _image_ready():
        pytest.skip("Docker image or daemon is unavailable")
    return DockerRunner(str(tmp_path / "executions"), "reponyx-executor:phase4")


def _request(
    execution_id: str, repository_id: str, command: tuple[str, ...], resources: ResourcePolicy
) -> ExecutionRequest:
    return ExecutionRequest(
        execution_id,
        repository_id,
        command,
        "",
        resources.timeout_seconds,
        EnvironmentPolicy(()),
        resources,
    )


def test_memory_limit_is_structured_and_cleaned(tmp_path: Path) -> None:
    runner = _runner(tmp_path)
    source = tmp_path / "memory"
    source.mkdir()
    (source / "test_memory.py").write_text(
        "def test_memory():\n"
        "    data = []\n"
        "    while True:\n"
        "        data.append(bytearray(4 * 1024 * 1024))\n"
    )

    result = runner.run(
        _request(
            "memory-limit",
            "repo-memory",
            ("python", "-m", "pytest", "-q"),
            ResourcePolicy(20, "64m", 1.0, 32, 10_000),
        ),
        source,
    )

    assert result.status.value == "resource_limited"
    assert result.resource_limited
    assert not (tmp_path / "executions" / "memory-limit").exists()
    assert not subprocess.run(
        ["docker", "ps", "-a", "--filter", "name=reponyx-memory-limit", "--format", "{{.ID}}"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()


def test_pid_limit_is_structured_and_cleaned(tmp_path: Path) -> None:
    runner = _runner(tmp_path)
    source = tmp_path / "pids"
    source.mkdir()
    (source / "test_pids.py").write_text(
        "import os\n"
        "from pathlib import Path\n"
        "def test_pids():\n"
        "    assert Path('/sys/fs/cgroup/pids.max').read_text().strip() == '8'\n"
        "    children = []\n"
        "    limited = False\n"
        "    for _ in range(256):\n"
        "        try:\n"
        "            children.append(os.fork())\n"
        "        except (AttributeError, OSError):\n"
        "            limited = True\n"
        "            break\n"
        "    for child in children:\n"
        "        if child == 0:\n"
        "            os._exit(0)\n"
        "    for child in children:\n"
        "        os.waitpid(child, 0)\n"
        "    assert limited\n"
    )

    result = runner.run(
        _request(
            "pid-limit",
            "repo-pids",
            ("python", "-m", "pytest", "-q", "-s"),
            ResourcePolicy(20, "256m", 1.0, 8, 10_000),
        ),
        source,
    )

    assert result.status.value in {"resource_limited", "failed"}
    assert not (tmp_path / "executions" / "pid-limit").exists()
    assert not subprocess.run(
        ["docker", "ps", "-a", "--filter", "name=reponyx-pid-limit", "--format", "{{.ID}}"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()


def test_output_limit_truncates_stdout_and_stderr(tmp_path: Path) -> None:
    runner = _runner(tmp_path)
    source = tmp_path / "output"
    source.mkdir()
    (source / "test_output.py").write_text(
        "import sys\n"
        "def test_output():\n"
        "    print('o' * 100000)\n"
        "    print('e' * 100000, file=sys.stderr)\n"
    )

    result = runner.run(
        _request(
            "output-limit",
            "repo-output",
            ("python", "-m", "pytest", "-q", "-s"),
            ResourcePolicy(20, "256m", 1.0, 32, 1_000),
        ),
        source,
    )

    assert result.output_truncated
    assert result.status.value == "resource_limited"
    assert len(result.stdout) <= 1_000
    assert len(result.stderr) <= 1_000
    assert not (tmp_path / "executions" / "output-limit").exists()


def test_concurrent_repositories_have_independent_sandboxes(tmp_path: Path) -> None:
    runner = _runner(tmp_path)
    sources: list[Path] = []
    for name in ("repo-a", "repo-b"):
        source = tmp_path / name
        source.mkdir()
        (source / "identity.txt").write_text(name)
        (source / "test_identity.py").write_text(
            "from pathlib import Path\n"
            "def test_identity():\n"
            f"    assert Path('identity.txt').read_text() == '{name}'\n"
            "    assert not Path('../repo-a/identity.txt').exists()\n"
            "    assert not Path('../repo-b/identity.txt').exists()\n"
        )
        sources.append(source)

    def run(index: int):
        return runner.run(
            _request(
                f"concurrent-{index}",
                f"repo-{index}",
                ("python", "-m", "pytest", "-q", "-s"),
                ResourcePolicy(20, "256m", 1.0, 32, 10_000),
            ),
            sources[index],
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, (0, 1)))

    assert [result.status.value for result in results] == ["completed", "completed"]
    assert results[0].execution_id != results[1].execution_id
    assert not list((tmp_path / "executions").iterdir())
    assert not subprocess.run(
        ["docker", "ps", "-a", "--filter", "name=reponyx-concurrent", "--format", "{{.ID}}"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()


def test_startup_failure_cleans_ephemeral_workspace(tmp_path: Path) -> None:
    if not _docker_ready():
        pytest.skip("Docker daemon is unavailable")
    runner = DockerRunner(str(tmp_path / "executions"), "reponyx-executor:image-does-not-exist")
    source = tmp_path / "startup"
    source.mkdir()

    result = runner.run(
        _request(
            "startup-failure",
            "repo-startup",
            ("python", "-m", "pytest", "-q"),
            ResourcePolicy(10, "256m", 1.0, 32, 1_000),
        ),
        source,
    )

    assert result.status.value == "failed"
    assert result.exit_code == 125
    assert result.error
    assert not (tmp_path / "executions" / "startup-failure").exists()
    assert not subprocess.run(
        ["docker", "ps", "-a", "--filter", "name=reponyx-startup-failure", "--format", "{{.ID}}"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()


def test_symlink_and_host_sentinel_do_not_escape_workspace(tmp_path: Path) -> None:
    runner = _runner(tmp_path)
    source = tmp_path / "symlinks"
    source.mkdir()
    outside = tmp_path / "outside-sentinel.txt"
    outside.write_text("host-secret-sentinel")
    try:
        (source / "parent-link").symlink_to(tmp_path, target_is_directory=True)
        (source / "absolute-link").symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    (source / "test_escape.py").write_text(
        "from pathlib import Path\n"
        "def test_escape():\n"
        "    assert not Path('/host-sentinel.txt').exists()\n"
        "    assert not Path('parent-link/outside-sentinel.txt').exists()\n"
        "    assert not Path('absolute-link').exists()\n"
    )

    result = runner.run(
        _request(
            "symlink-matrix",
            "repo-symlink",
            ("python", "-m", "pytest", "-q"),
            ResourcePolicy(20, "256m", 1.0, 32, 10_000),
        ),
        source,
    )

    assert result.status.value == "completed"
