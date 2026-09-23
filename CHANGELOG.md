# Changelog

## v0.1.0 — 2026-09-23

Initial release.

### Added

**Repository Intelligence**
- Repository intake with HTTPS cloning and workspace isolation
- Tree-sitter code parsing for 6 languages (Python, JavaScript, TypeScript, Java, Go, Rust)
- Symbol extraction: functions, classes, methods, interfaces, types, imports, exports
- Repository maps with languages, package managers, entry points, tests, and config files
- Logical symbol-based code chunks for retrieval

**Codebase RAG**
- Hybrid retrieval engine (lexical + semantic search)
- Deterministic, OpenAI, and Ollama embedding providers
- Repository-scoped vector indexing
- Query rewriting with deterministic fallback
- Metadata filters by language, file path, and symbol type
- Source attribution with exact file, symbol, and line-range references
- Hybrid ranking (65% semantic, 35% lexical default)

**Investigation**
- LangGraph investigation workflow with explicit stop conditions
- Retrieval, source inspection, symbol lookup, and dependency tools
- Structured evidence collection with supported/contradicted/inconclusive states
- Root-cause analysis with evidence-backed confidence levels
- Investigation persistence and history API

**Repair**
- Deterministic keyword-matching repair model
- LLM-based repair proposals (Ollama, OpenAI providers)
- Ephemeral repair workspaces (canonical repository never modified)
- Patch validation: path traversal, symlink, hash, size, and file-count checks
- Filesystem-derived unified diffs
- Diff persistence in database
- Bounded repair iterations with failure analysis
- Repair reports with changed files, diff, and verification level

**Docker Test Execution**
- Docker-only sandbox with dedicated non-root image
- Network-disabled execution (`--network none`)
- CPU, memory, PID, timeout, and output limits
- Test-command allowlist (pytest, npm test, go test, cargo test)
- Container and workspace cleanup on every exit path
- Structured test results and execution evidence

**Review Workflow**
- Pending-review, approve, reject, and cancel states
- Evidence-backed repair reports
- Diff persistence through review cycle
- Review API endpoints

**Frontend (Next.js)**
- Repository management pages
- Investigation detail with evidence chain and root-cause analysis
- Repair detail with timeline, diff viewer, and tabs
- Review workflow with approve/reject
- LLM provider health monitoring
- Evaluation dashboard
- Settings and configuration
- Responsive sidebar with health status

**API**
- Repository CRUD and analysis endpoints
- Investigation creation and retrieval
- Repair creation, diff, and review endpoints
- LLM health and provider status
- CORS configuration via environment variable

**Infrastructure**
- PostgreSQL and SQLite support
- Configurable CORS origins (`REPONYX_CORS_ORIGINS`)
- Docker Compose development stack
- Execution Dockerfile with Python 3.13
- Environment-based configuration (`.env.example`)
- MIT License

**Testing**
- 108 unit tests
- Ruff lint and format validation
- TypeScript compilation and ESLint
- Demo repository: [demo-buggy-calculator](https://github.com/najaraasif/demo-buggy-calculator)

### Known Limitations

- Repair workspaces are ephemeral; diff is persisted but workspace is cleaned after completion
- Deterministic repair rules cover specific known patterns; LLM-based repair is the broader path
- Single-repo scope; cross-repo repairs not supported
- No Git operations (pull requests, merges, deployment)
- No authentication or role-based authorization
- Real LLM provider benchmarks require API keys or local Ollama
