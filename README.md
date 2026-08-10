# Q-GATE AI

**Don’t let bad code reach the branch.**

LangGraph-powered quality gate: understands the git change, scores risk, selects relevant tests, runs them, classifies failures, and enforces a deterministic PASS / WARN / BLOCK policy.

This is not a demo chatbot. Analysis runs against the **real repository** you point at (`--path`), using real `git diff`, real file contents, real pytest/Playwright processes, and real SQLite/Postgres memory.

---

## Documentation (start here for pipelines)

| Doc | What it covers |
|------|----------------|
| **[docs/PIPELINE_INTEGRATION.md](docs/PIPELINE_INTEGRATION.md)** | Connect to GitHub Actions, GitLab CI, Azure DevOps, Jenkins, pre-push hooks — exit codes, secrets, caching, branch protection, troubleshooting |
| **[docs/CONFIGURATION.md](docs/CONFIGURATION.md)** | Every `qgate.yaml` key explained |
| **[docs/README.md](docs/README.md)** | Doc index + copy-paste pipeline file locations |

Ready-made pipeline YAML:

- `integrations/github/qgate.yml`
- `integrations/gitlab/.gitlab-ci-qgate.yml`
- `integrations/azure_devops/azure-pipelines-qgate.yml`
- `integrations/jenkins/Jenkinsfile`

---

## What runs on a real change

```text
git refs (base → head)
        ↓
Repository discovery (language, test framework, layout)
        ↓
Git change analysis (files, diff, stats)
        ↓
Semantic symbols (AST / heuristics)
        ↓
Parallel intelligence
  • Security (secrets, injection patterns, optional Bandit)
  • Dependencies (manifest changes)
  • AI code review (heuristics; LLM if OPENAI_API_KEY set)
  • Test impact (P0–P3 selection)
  • Regression risk (critical paths, missing tests)
  • Historical memory (hotspots, prior failures, block rate)
        ↓
Validation plan → targeted test execution (pytest / Playwright / …)
        ↓
Failure investigator (if tests failed)
        ↓
Quality + risk scores → Policy engine → PASS | PASS_WITH_WARNINGS | BLOCK
        ↓
Persist to quality memory → JSON / MD / HTML reports
```

---

## Install

```bash
cd qgate-ai
python3.12 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
export PYTHONPATH=.
```

Requires **Python 3.12+** and a **git** working tree for the target application.

---

## Run against a real application repo

```bash
# From the application repository root (must contain .git)
git fetch origin main

qgate check --base origin/main --head HEAD
# or
python -m apps.cli.main check --base origin/main --head HEAD --path /absolute/path/to/app
```

### Exit codes (wire these into CI)

| Code | Meaning |
|------|---------|
| **0** | PASS or PASS_WITH_WARNINGS |
| **1** | BLOCK |
| **2** | Configuration error |
| **3** | Tool / runtime error |

### Outputs (written every run)

```text
.qgate/reports/qgate-report.json
.qgate/reports/qgate-report.md
.qgate/reports/qgate-report.html
.qgate/memory.db                  # if memory.enabled
```

---

## Pipeline (short version)

Full detail: **[docs/PIPELINE_INTEGRATION.md](docs/PIPELINE_INTEGRATION.md)**.

**GitHub Actions:** copy `integrations/github/qgate.yml` → `.github/workflows/qgate.yml`, set optional secret `OPENAI_API_KEY`, require the job on branch protection.

**Pattern every platform uses:**

```bash
git fetch origin <target-branch> --depth=50
pip install -e .   # or pip install qgate-ai from your registry
# install the *application* test deps first (requirements.txt / npm ci)
qgate check --base origin/<target-branch> --head <commit-sha>
```

---

## Configuration

Commit `qgate.yaml` in each application repository. See **[docs/CONFIGURATION.md](docs/CONFIGURATION.md)**.

Critical policy knobs:

```yaml
quality_gate:
  minimum_quality_score: 80
  maximum_risk_score: 60
  block_on:
    - critical_security
    - secret_detected
    - targeted_test_failure
    - critical_regression

memory:
  enabled: true
  backend: sqlite
  path: .qgate/memory.db
```

Optional LLM review:

```bash
export OPENAI_API_KEY=sk-...
```

Without the key, security heuristics, test selection, execution, and policy still run.

---

## CLI

```bash
qgate init                 # create qgate.yaml
qgate check --base origin/main --head HEAD
qgate report               # list last report paths
qgate memory-stats
qgate suppress <fingerprint> --status false_positive
qgate version
```

---

## Implemented phases

| Phase | Scope | Status |
|-------|--------|--------|
| 1 | LangGraph state, git, discovery, scoring, policy, CLI, reports | Done |
| 2 | Security, dependency, code review, test impact, regression, parallel agents | Done |
| 3 | Validation planner, test runner, failure investigator, conditional edges | Done |
| 4 | Quality memory (SQLite), historical agent, Playwright runner | Done |
| 5 | React dashboard | Not started |
| 6 | Packaged CI adapters beyond YAML templates | Templates only (see `integrations/`) |

---

## Tests

```bash
export PYTHONPATH=.
pytest tests/unit -q
```

Unit tests cover policy, scoring, security scanner, test impact, runner, failure investigator, and memory store — against temporary real filesystems and subprocess pytest.

---

## License

MIT
