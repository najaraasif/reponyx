# Security Model

Reponyx treats repository files, issue text, generated code, tool output, and retrieved context as untrusted input.

## Boundaries

- The API process is not a repository execution environment.
- Repository code is never executed directly on the host.
- Future command execution will occur through a policy-enforcing gateway and Docker sandbox.
- Workspaces will be temporary, scoped per run, and cleaned up on success and failure.
- Secrets will be passed only through explicit allowlisted configuration and never mounted into repository containers.
- Network access in execution sandboxes will be disabled by default.
- GitHub write operations will require explicit user approval.

## Required controls before execution phases

- Resolve and validate paths beneath the run workspace; reject traversal and unsafe symlinks.
- Apply command allow/deny policy, timeout, CPU, memory, process, and output limits.
- Use a non-root container user where practical.
- Drop unnecessary Linux capabilities and use a read-only base filesystem where practical.
- Disable network unless a task explicitly requires it and policy permits it.
- Clean up containers, processes, mounts, and temporary credentials on every exit path.
- Record structured audit events without recording secrets or private chain-of-thought.

Phase 1 exposes read-only repository intake and static analysis. It accepts only HTTPS `github.com/{owner}/{repository}` URLs, performs a shallow clone with tags disabled, and never installs packages, invokes build systems, runs tests, or executes source code. Source files stay in a per-repository workspace; PostgreSQL stores metadata and analysis summaries rather than source contents.

The analyzer skips symlinks, binary extensions, unsupported files, hidden/generated directories, oversized files, and oversized repositories. Paths are normalized as repository-relative POSIX paths and traversal is rejected. Tree-sitter parse errors are isolated to the affected file and recorded in `parse_failures`.

Phase 2 preserves repository isolation in the vector layer: every vector write and search is keyed by repository ID before language, path, or symbol filters are applied. Search results contain exact source attribution. Provider selection is configuration-driven; credentials are never returned or logged. The deterministic provider sends no source outside the process. OpenAI and Ollama providers are opt-in and may send normalized chunk text to the configured service, so deployment policy must explicitly permit that behavior.

The retrieval subsystem does not execute repository code or modify workspaces. It stores indexed chunk content for retrieval responses, scoped by repository ID; it does not store complete repository trees in the metadata record.

Phase 3 investigation tools are strictly read-only. They expose retrieval, metadata, structure, symbol, reference, dependency, and bounded source inspection only. Source inspection resolves a repository-relative path beneath the persisted workspace, rejects traversal and symlinks, limits file size and line ranges, and never exposes unrestricted filesystem paths. The LangGraph workflow contains no shell, Git, test, write, patch, commit, push, or dependency-installation tool. Issues and source text remain untrusted input, and only concise structured events are logged.

Phase 4 adds execution only through the execution gateway. The API accepts a framework identifier, not a command string. The gateway maps it to an allowlisted argv and rejects shell metacharacters, executable replacement, traversal, absolute paths, privilege tools, network tools, Docker commands, and Git write commands. The canonical workspace is never mounted; an ephemeral copy is mounted read-only into a dedicated Docker image. The container has no application secrets, no Docker socket, no network by default, dropped capabilities, no-new-privileges, CPU/memory/PID limits, timeout enforcement, bounded output, and forced cleanup.

The normal test suite uses a fake runner and does not require Docker or network access. Dedicated integration tests skip when Docker is unavailable or the pinned execution image is not built. A Docker-backed result is not considered verified by unit tests alone.

Execution persistence stores only output already bounded by the execution resource policy. The canonical repository workspace is never passed to Docker; each execution receives a unique ephemeral copy that is deleted after completion. Docker integration verification is now available through the installed Docker Desktop WSL 2 runtime.

## Phase 4 Sandbox Verification

Verification was rerun after installing Docker Desktop per-user with the WSL 2 backend.

Measured environment:

- Windows 11 Pro x64.
- WSL 2 version 2.3.26.
- Docker Desktop 4.91.0.
- Docker Engine 29.8.0.
- Linux container context `desktop-linux`.
- Execution image: `reponyx-executor:phase4`.
- Final image digest: `sha256:15525726aa9c4d9669c9b8790c1c5943008745b87d65b3adb1d38c79249bbf83`.

Verified:

- Image builds successfully.
- Image starts successfully.
- Container user is UID `65532`, not root.
- `pytest`, `ruff`, and `mypy` are available in the image.
- `/bin/sh` and `/usr/bin/sh` are absent from the final image.
- Approved pytest executes through `DockerRunner` inside Docker.
- Canonical workspace is copied to a unique ephemeral execution directory.
- Repository mount is read-only.
- A harmless write to the repository mount is denied.
- Network access is unavailable with `--network none`.
- OpenAI, GitHub, database, and application sentinel secrets are absent.
- No Docker socket is mounted.
- The container has no host environment pass-through.
- Timeout execution returns `timed_out`.
- Timeout execution removes the ephemeral workspace.
- Timeout execution removes the container.
- Successful execution removes the container and workspace.
- Read-only security, network, cleanup, and timeout matrix passed.
- Docker integration suite: 10 passed.
- Memory-limit fixture returned `resource_limited` and cleaned the container/workspace.
- PID-limit fixture verified `pids.max=8`, terminated safely, and cleaned the container/workspace.
- Output-limit fixture bounded stdout/stderr, set `output_truncated=true`, returned `resource_limited`, and cleaned up.
- Concurrent two-repository fixture completed both executions with independent IDs/workspaces/containers and no cross-repository visibility.
- Invalid-image startup fixture returned a structured failed result with exit code 125 and cleaned the workspace/container state.
- Symlink and host-sentinel fixture passed without workspace escape.

The following remain outside this verification matrix: arbitrary production-scale workload behavior, long-duration concurrency beyond two active containers, and host-specific virtualization failure modes. The requested Phase 4.6 residual-risk matrix is verified. Phase 5 remains blocked by instruction and was not implemented.

## Phase 5 Repair Security

Phase 5 introduces writes only inside a fresh repair workspace copied from the canonical repository. The canonical workspace is never used as a patch target. Patch paths are repository-relative, traversal-checked, symlink-rejected, hash-recorded, and bounded by file, line, deletion, creation, and total-size limits. Changes are applied only after validation, and the final unified diff is generated from the actual repair filesystem.

All repair tests use the Phase 4 execution gateway through a distinct repair workspace path. No repair code invokes a shell or host process directly. Issue text and repository content remain untrusted data; source comments such as `ignore previous instructions` are never treated as control instructions. The repair model returns structured file operations only, and model-generated paths cannot modify configuration, execution policy, or security controls outside the repair workspace.

Repair workspaces are cleaned after completion or cancellation. No Git commit, push, pull request, merge, production deployment, or automatic approval is implemented.

## Phase 6 LLM Verification

Phase 6 uses the existing repair workspace, patch validator, and Docker execution gateway. The normal provider is `mock`; no external OpenAI call is made by the normal suite or benchmark. OpenAI is opt-in through `REPONYX_LLM_PROVIDER=openai` and `REPONYX_OPENAI_API_KEY`.

Measured offline/mock results:

- Full suite: 74 passed.
- Docker security integration suite: 10 passed.
- Mocked LLM structured-output tests: 4 passed.
- Deterministic repair benchmark: 1 case, patch application success 1.0, repair success 1.0, one iteration.
- Real-provider benchmark: not run because no provider credential was used.
- Deterministic 20-query retrieval evaluation: lexical Recall@5 0.45, Precision@5 0.21, MRR 0.542; semantic Recall@5 1.00, Precision@5 0.42, MRR 0.663; hybrid Recall@5 1.00, Precision@5 0.44, MRR 0.738.

The LLM context builder inserts an explicit untrusted-data boundary and enforces a character budget. Provider calls are bounded by timeout, output token, and per-repair call settings. Invalid structured output fails before patch validation/application. No provider output can bypass workspace, path, patch-size, command, or Docker policy.

Phase 7 keeps the Phase 4-6 boundaries: retrieval is repository-scoped, all changes remain in repair workspaces, all tests use the Docker gateway, and structured failure/decision data cannot override hard iteration, patch, command, or resource limits. Real OpenAI results are not represented unless an explicit credentialed integration run is performed.

Phase 8 operational jobs do not change the repair security model. Background execution uses a bounded in-process executor, repair cancellation prevents future work at the service boundary, and review approval changes only review state. No approval action modifies the canonical repository or performs Git operations.

## Phase 6 LLM Security

LLM calls are opt-in and bounded by `REPONYX_LLM_TIMEOUT_SECONDS`, `REPONYX_LLM_MAX_OUTPUT_TOKENS`, `REPONYX_LLM_MAX_CALLS`, and `REPONYX_LLM_MAX_CONTEXT_CHARACTERS`. The normal suite uses mock providers and requires no API key. Provider credentials are never logged or persisted in repository metadata.

The context prompt explicitly classifies issue text, source files, comments, README content, tests, and retrieved documentation as untrusted data. Prompt-injection text cannot authorize commands, change patch policy, bypass validation, expose secrets, or modify security controls. The model returns structured file operations only; the existing Phase 5 patch validator rejects unsafe paths, symlinks, excessive changes, and workspace escapes.

OpenAI is the first external provider and is disabled by default. Normalized relevant context may be sent to the configured provider only when explicitly enabled. Unrelated source, host paths, environment variables, credentials, Docker configuration, and authorization headers are not included in the assembled context.

Ollama is a local provider option. Provider health reports availability/model status without exposing sensitive configuration. If Ollama is unavailable or the configured model is missing, Reponyx reports the provider failure and does not silently fall back to mock behavior.

Phase 10 verification found no Ollama CLI/service in the execution environment. The local provider was verified with mocked HTTP responses and connection-failure diagnostics only; no real Ollama model output is claimed.

## Threats considered

- Prompt injection in issues, source comments, documentation, and test output.
- Malicious build scripts and package installation hooks.
- Path traversal, symlink escapes, and workspace contamination.
- Secret exfiltration through logs, diffs, or generated reports.
- Resource exhaustion and fork bombs.
- Network-based data exfiltration.
- Unauthorized GitHub pushes or pull requests.
