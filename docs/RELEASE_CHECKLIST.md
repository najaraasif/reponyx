# Release Checklist

Pre-release verification for Reponyx v1.0.0.

## Automated Checks

- [ ] `python -m pytest` passes (67+ unit tests)
- [ ] `python -m pytest tests/integration -m integration` passes (10 Docker tests)
- [ ] `python -m ruff check .` passes
- [ ] `python -m ruff format --check .` passes
- [ ] `python -m mypy src` passes

## Security

- [ ] Secret scan completed (no API keys, tokens, passwords, credentials)
- [ ] No `.env` files tracked
- [ ] No local databases tracked (`.db`, `.sqlite`)
- [ ] No workspace directories tracked
- [ ] No evaluation artifacts tracked
- [ ] Docker execution image uses non-root user
- [ ] Docker execution image has no shell
- [ ] Docker tests verify `--network none`
- [ ] Docker tests verify no Docker socket mount
- [ ] Docker tests verify credential isolation
- [ ] Patch validation rejects traversal and symlinks
- [ ] Canonical repository immutability verified

## Documentation

- [ ] README.md reviewed for portfolio quality
- [ ] Architecture diagram reviewed and accurate
- [ ] Security section accurate and complete
- [ ] Measured results clearly labeled as fixture-scale
- [ ] Limitations section honest and complete
- [ ] Demo guide (docs/DEMO.md) complete and reproducible
- [ ] CHANGELOG.md includes rename and all phases
- [ ] CONTRIBUTING.md updated with new package name

## Assets

- [ ] Dashboard screenshot captured
- [ ] Health endpoint screenshot captured
- [ ] Repository analysis screenshot captured
- [ ] RAG search screenshot captured
- [ ] Investigation report screenshot captured
- [ ] Repair diff screenshot captured
- [ ] Review state screenshot captured
- [ ] Docker sandbox verification screenshot captured

## Git & GitHub

- [ ] Git initialized (`git init`)
- [ ] Initial commit created
- [ ] GitHub repository created (name: `reponyx`)
- [ ] Repository description set: "AI software engineering agent for repository intelligence, RAG-powered investigation, secure code repair, and human-reviewed verification."
- [ ] Topics added: `ai-agent`, `rag`, `llm`, `langgraph`, `tree-sitter`, `fastapi`, `docker`, `code-repair`, `ollama`, `python`, `software-engineering`
- [ ] README screenshots added
- [ ] v1.0.0 release created
- [ ] Repository pinned to GitHub profile

## Recommended First Commit Message

```
feat: initial release of Reponyx AI software engineering agent

Reponyx is an AI software engineering agent that analyzes GitHub
repositories, retrieves relevant code using hybrid RAG, diagnoses
bugs through structured investigation, generates validated patches,
executes tests in an isolated Docker sandbox, and produces
evidence-backed repair reports for human review.

Implemented features:
- Tree-sitter code intelligence (Python, JS, TS, Java, Go, Rust)
- Hybrid lexical/semantic RAG with source attribution
- LangGraph investigation workflow
- Ephemeral repair workspaces with patch validation
- Docker sandbox execution with resource limits
- Mock, Ollama, and OpenAI provider support
- Operational dashboard and repair history API
```

## Recommended GitHub Topics

```
ai-agent rag llm langgraph tree-sitter fastapi docker code-repair ollama python software-engineering
```
