# Reponyx

**AI Software Engineering Agent**

Investigate repository issues. Collect source evidence. Identify root causes. Generate minimal repairs. Run tests in isolation. Review the resulting changes.

```
Repository
    ↓
Investigation
    ↓
Evidence
    ↓
Root Cause
    ↓
Repair
    ↓
Docker
    ↓
Tests
    ↓
Review
```

## What Reponyx Does

Reponyx takes a repository issue description, inspects the codebase, retrieves relevant evidence, identifies the root cause, generates a minimal patch, executes tests inside an isolated Docker sandbox, and sends the change through human review.

It is not a generic chatbot. It is a controlled software-engineering system built around repository intelligence, source-attributed retrieval, structured investigation, ephemeral repair workspaces, Docker test execution, bounded iteration, and human review.

## Engineering Highlights

| Capability | Implementation |
| --- | --- |
| **Agentic workflow** | LangGraph state machine for investigation and repair with explicit stop conditions |
| **Code intelligence** | Tree-sitter parsing across 6 languages with symbol, import, export, and dependency extraction |
| **RAG retrieval** | Hybrid lexical + semantic search with query rewriting, reranking, and source attribution |
| **LLM structured outputs** | Provider-neutral abstraction with bounded context, token limits, and call budgets |
| **Patch validation** | Path traversal protection, symlink rejection, size limits, and hash verification before application |
| **Secure execution** | Docker-only sandbox with `--network none`, non-root user, no shell, no Docker socket |
| **Resource limits** | CPU, memory, PID, timeout, and output truncation with enforced cleanup |
| **Human review** | Pending-review, approve, reject, and cancel states with evidence-backed reports |

## Demo

Try Reponyx with the [demo-buggy-calculator](https://github.com/najaraasif/demo-buggy-calculator) — a Python module with 5 intentional bugs.

```bash
# Start services
docker compose up -d
cd frontend && npm run dev &
uvicorn reponyx.main:app --reload

# Add the demo repo
curl -X POST http://127.0.0.1:8000/repositories \
  -H "Content-Type: application/json" \
  -d '{"url": "https://github.com/najaraasif/demo-buggy-calculator.git"}'

# Analyze it
curl -X POST http://127.0.0.1:8000/repositories/{ID}/analyze \
  -H "Content-Type: application/json" -d '{"deep": true}'

# Investigate and repair
curl -X POST http://127.0.0.1:8000/repositories/{ID}/repairs \
  -H "Content-Type: application/json" \
  -d '{"issue": "average uses integer division instead of true division"}'

# Review the diff
curl http://127.0.0.1:8000/repairs/{REPAIR_ID}/diff
```

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Frontend    │────▶│  FastAPI      │────▶│  Repository     │
│  (Next.js)  │     │  Backend      │     │  Intake         │
└─────────────┘     └──────────────┘     └────────┬────────┘
                                                   │
                    ┌──────────────────────────────┘
                    ▼
          ┌──────────────────┐     ┌──────────────────┐
          │  Tree-sitter      │────▶│  Hybrid RAG       │
          │  Code Intelligence│     │  Retrieval        │
          └──────────────────┘     └────────┬─────────┘
                                            │
                    ┌───────────────────────┘
                    ▼
          ┌──────────────────┐     ┌──────────────────┐
          │  Investigation    │────▶│  Repair           │
          │  (LangGraph)      │     │  (LangGraph)      │
          └──────────────────┘     └────────┬─────────┘
                                            │
                    ┌───────────────────────┘
                    ▼
          ┌──────────────────┐     ┌──────────────────┐
          │  Docker Sandbox   │────▶│  Repair Report    │
          │  (Test Execution) │     │  + Human Review   │
          └──────────────────┘     └──────────────────┘
```

## Capabilities

### Repository Intelligence

- Safe HTTPS GitHub intake and shallow cloning
- Tree-sitter parsing for **Python, JavaScript, TypeScript, Java, Go, and Rust**
- Functions, classes, methods, interfaces, types, imports, exports, decorators, and source locations
- Repository maps with languages, package managers, entry points, tests, and configuration files
- Logical symbol-based code chunks

### Codebase RAG

- Deterministic, OpenAI, and Ollama embedding providers
- Repository-scoped vector indexing
- Code-aware lexical search
- Semantic search with configurable weights
- Hybrid ranking (default: 65% semantic, 35% lexical)
- Query rewriting with deterministic fallback
- Metadata filters by language, file path, and symbol type
- Exact file, symbol, line-range, and chunk attribution

### Investigation

- Explicit LangGraph investigation workflow
- Retrieval, source inspection, symbol lookup, and static dependency tools
- Structured evidence and hypotheses
- Supported, contradicted, and inconclusive verification states
- Evidence-based confidence levels (high / medium / low)
- Root-cause investigation reports

### Repair

- Ephemeral repair workspaces (canonical repository never modified)
- Deterministic keyword-matching repair model with file-level replacement
- LLM-based repair proposals (Ollama, OpenAI)
- Path, symlink, hash, file-count, line-count, and size validation
- Filesystem-derived unified diffs
- Bounded repair iterations (configurable max)
- Failure-driven repair state with structured root-cause, plan, and failure analysis

### Docker Test Execution

- Explicit test-command allowlist (pytest, npm test, go test, cargo test)
- Docker-only execution with dedicated non-root image
- Read-only repository mount
- Network disabled (`--network none`)
- CPU, memory, PID, timeout, and output limits
- Container and workspace cleanup on every exit path

## Security Model

```text
LLM proposes
  -> system validates paths, sizes, and hashes
  -> changes apply only in ephemeral workspace
  -> Docker executes approved tests (network=none, non-root)
  -> filesystem produces the diff
  -> tests provide evidence
  -> human reviews
```

| Property | Status |
| --- | --- |
| Canonical repository never modified | Verified |
| Ephemeral repair workspace per session | Verified |
| Docker non-root (UID 65532), no shell | Verified |
| Network disabled by default | Verified |
| No Docker socket mounted | Verified |
| CPU / memory / PID limits enforced | Verified |
| Patch path validation (traversal, symlink, hash) | Verified |
| Human review required before approval | Verified |

See [SECURITY.md](SECURITY.md) for the complete security model.

## Setup

Requirements: Python 3.12+, Docker Desktop, PostgreSQL (or SQLite for tests).

```bash
# Clone
git clone https://github.com/najaraasif/reponyx.git
cd reponyx

# Backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn reponyx.main:app --reload

# Frontend
cd frontend && npm install && npm run dev
```

### Verify

```bash
curl http://127.0.0.1:8000/healthz
# → true
```

### Docker Execution Image

```bash
docker build -f execution.Dockerfile -t reponyx-executor:phase4 .
```

## Tests

```bash
python -m pytest                    # Unit tests (no Docker required)
python -m ruff check .              # Lint
python -m ruff format --check .     # Format
```

108 unit tests passing. Lint and format clean.

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — Component responsibilities and data flow
- [SECURITY.md](SECURITY.md) — Trust boundaries and Docker verification
- [CONTRIBUTING.md](CONTRIBUTING.md) — Development setup and change rules
- [CHANGELOG.md](CHANGELOG.md) — Release history
- [docs/DEMO.md](docs/DEMO.md) — Portfolio demo capture guide

## Limitations

- **Ephemeral workspaces**: Repair workspaces are temporary. The diff is persisted in the database, but the workspace itself is cleaned up after repair completion.
- **Deterministic repair rules**: Currently cover specific known issue patterns. LLM-based repair is the broader path for arbitrary issues.
- **Single-repo scope**: Each repair targets one repository. Cross-repo repairs are not supported.
- **No Git operations**: No pull requests, merges, deployment, or automatic approval.
- **No authentication**: Role-based authorization is not implemented.

## License

MIT
