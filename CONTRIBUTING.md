# Contributing

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
pre-commit install
```

## Checks

Run the full local check set before opening a change:

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy src
```

## Local LLM Checks

Ollama checks are opt-in. Set `REPONYX_LLM_PROVIDER=ollama` and start Ollama locally when validating the local provider. OpenAI validation is never required for normal CI.

## Change rules

- Keep modules focused and use strong types.
- Add tests for behavior and security boundaries.
- Do not add provider keys, repository data, or generated artifacts.
- Do not expose private chain-of-thought; expose concise summaries and evidence.
- Keep phase boundaries explicit. A later-phase capability must be approved before implementation.
