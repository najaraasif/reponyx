# Portfolio Demo Guide

This guide describes a truthful employer-facing demonstration of the implemented system. It uses the deterministic mock provider and does not claim real LLM performance.

## Prerequisites

- Python 3.12+
- Docker Desktop running
- The execution image built

## Setup

```powershell
# Build the execution image
docker build -f execution.Dockerfile -t reponyx-executor:phase4 .

# Install dependencies
python -m pip install -e ".[dev]"

# Start the API
python -m uvicorn reponyx.main:app --reload
```

In a separate terminal, open `dashboard/index.html` through a static server.

## Demo Sequence

### Step 1: Health Check

```powershell
Invoke-RestMethod http://127.0.0.1:8000/healthz
```

Shows: service name, version, environment, status.

### Step 2: Ingest a Repository

```powershell
$body = @{ url = "https://github.com/psf/requests" } | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8000/repositories -Method POST -Body $body -ContentType "application/json"
```

Shows: repository ID, URL, status.

### Step 3: Analyze the Repository

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/repositories/{repository_id}/analyze" -Method POST
```

Shows: languages detected, files analyzed, symbols extracted, dependencies mapped.

### Step 4: Index for RAG

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/repositories/{repository_id}/index" -Method POST
```

Shows: chunks indexed, embedding provider, index status.

### Step 5: Search Code

```powershell
$body = @{ query = "password reset"; top_k = 5 } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8000/repositories/{repository_id}/search" -Method POST -Body $body -ContentType "application/json"
```

Shows: source-attributed results with file paths, line ranges, and relevance scores.

### Step 6: Investigate an Issue

```powershell
$body = @{ issue = "Password reset function is not sending emails" } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8000/repositories/{repository_id}/investigations" -Method POST -Body $body -ContentType "application/json"
```

Then retrieve the report:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/investigations/{investigation_id}/report"
```

Shows: evidence, affected files, hypotheses, confidence level, root-cause summary.

### Step 7: Create a Repair

```powershell
$body = @{ issue = "Password reset function is not sending emails" } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8000/repositories/{repository_id}/repairs" -Method POST -Body $body -ContentType "application/json"
```

### Step 8: Show the Diff

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/repairs/{repair_id}/diff"
```

Shows: unified diff generated from the ephemeral repair workspace, file changes, line counts.

### Step 9: Show Repair Report

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/repairs/{repair_id}/report"
```

Shows: root cause, repair plan, iterations, test results, evidence, status.

### Step 10: Show Review State

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/repairs/{repair_id}/review"
```

Shows: pending_review status, repair summary, ready for human approval.

### Step 11: Show Canonical Repository Unchanged

```powershell
git -C /path/to/cloned/repo status  # Should show clean working tree
```

Shows: the original repository was never modified.

### Step 12: Dashboard

Open `dashboard/index.html` and click Refresh.

Shows: total repairs, successful count, pending review, provider status.

## What the Demo Proves

| Claim | Evidence |
| --- | --- |
| Repository intelligence | Tree-sitter parses 6 languages, extracts symbols and dependencies |
| RAG retrieval | Hybrid search returns source-attributed results |
| Investigation | Structured evidence, hypotheses, and confidence levels |
| Repair proposal | LLM generates structured file changes |
| Patch validation | Path, size, and hash checks before application |
| Ephemeral workspace | Changes apply in isolated copy, not canonical repo |
| Docker execution | Tests run in sandbox with network disabled, non-root |
| Failure analysis | Structured failure data drives bounded repair iterations |
| Human review | Pending-review state blocks automatic approval |
| Evidence-backed | Diff, test results, and report all derived from actual execution |

## Claims Checklist

Claims supported by the repository:

- Tree-sitter repository intelligence across 6 languages
- Hybrid code retrieval with source attribution
- LangGraph-based investigation with structured evidence
- Structured repair proposals from LLM providers
- Patch validation with path, size, and hash checks
- Ephemeral repair workspaces (canonical repo immutable)
- Docker-isolated test execution with resource limits
- Failure-driven repair with bounded iterations
- Human-review boundary before approval
- Mock provider for deterministic offline testing
- Ollama provider for local inference (when available)
- OpenAI provider for cloud inference (when configured)

Do not claim:

- Real OpenAI benchmark performance (no API key configured)
- Real Ollama repair performance (Ollama unavailable in verification)
- Production deployment or reliability
- Automatic pull requests or merges
- Large-scale benchmark results from current fixture dataset
- Multi-file or cross-module repair capabilities

## Suggested Screenshot Locations

For a complete portfolio, capture and add:

1. `docs/screenshot-health.png` - Health endpoint response
2. `docs/screenshot-repository.png` - Repository analysis result
3. `docs/screenshot-search.png` - RAG search with source attribution
4. `docs/screenshot-investigation.png` - Investigation report with evidence
5. `docs/screenshot-diff.png` - Generated repair diff
6. `docs/screenshot-review.png` - Pending review state
7. `docs/screenshot-dashboard.png` - Dashboard overview
8. `docs/screenshot-security.png` - Docker sandbox verification
