# Q-GATE AI — Configuration Reference (`qgate.yaml`)

Every setting below is read from the application repository’s `qgate.yaml`.
There are no hidden defaults that silently change policy in production beyond what is documented here.

---

## Loading order

1. Path passed as `--config /path/to/qgate.yaml`
2. `./qgate.yaml` in the current working directory
3. `./.qgate/qgate.yaml`
4. Built-in defaults (same structure as the packaged `qgate.yaml`)

---

## `project`

| Key | Type | Purpose |
|-----|------|---------|
| `name` | string | Human name in reports |
| `description` | string | Optional |

---

## `quality_gate` (decision policy)

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `minimum_quality_score` | float | 80 | Below this → contributes to **BLOCK** |
| `maximum_risk_score` | float | 60 | Above this → warning; ≥80 → hard block path |
| `minimum_ai_confidence` | float | 0.75 | Reserved for human-in-the-loop thresholds |
| `block_on` | list[str] | see below | Categories that force **BLOCK** |
| `warnings` | list[str] | — | Informational categories |
| `require_full_regression_when` | object | — | Expand test selection |

### `block_on` values recognized by the policy engine

| Value | Effect |
|-------|--------|
| `critical_security` | High/critical security findings block |
| `secret_detected` | Hardcoded secret patterns block |
| `targeted_test_failure` | Failed selected tests block |
| `critical_regression` | Classified REAL_REGRESSION blocks |
| `build_failure` / `compilation_failure` | Reserved for build integration |

Example:

```yaml
quality_gate:
  minimum_quality_score: 80
  maximum_risk_score: 60
  block_on:
    - critical_security
    - secret_detected
    - targeted_test_failure
    - critical_regression
  require_full_regression_when:
    risk_score: 75
    changed_files: 25
    critical_area_changed: true
```

---

## `analysis` (feature flags)

| Key | Default | Effect when `false` |
|-----|---------|---------------------|
| `security` | true | Skip security scanner |
| `dependencies` | true | Skip dependency analysis |
| `historical_analysis` | true | Skip memory-backed history |
| `test_impact_analysis` | true | Skip test discovery/selection |
| `ai_code_review` | true | Skip heuristics + LLM review |
| `semantic_impact` | true | Skip symbol extraction |
| `architecture` | true | Reserved |

---

## `scoring`

Weights must sum approximately to 1.0 for interpretability (not enforced).

Quality dimensions: `code_quality`, `test_health`, `security`, `regression_risk`, `architecture`, `dependency_health`, `ai_confidence`.

Risk dimensions: `change_size`, `complexity`, `criticality`, `historical_failure`, `test_coverage`, `dependency_impact`, `security_impact`.

---

## `execution`

| Key | Purpose |
|-----|---------|
| `max_parallel_tests` | Reserved for future parallel runner |
| `timeout_minutes` | Hard timeout for the test subprocess |
| `sandbox` | Intent flag (path confinement already enforced) |
| `allowlist_commands` | Only these runner names may execute |

Default allowlist includes: `pytest`, `python`, `npm`, `npx`, `mvn`, `gradle`, `go`, `dotnet`.

Playwright uses `npx` → must remain allowlisted.

---

## `llm`

| Key | Purpose |
|-----|---------|
| `provider` | `openai` (others stubbed for extension) |
| `model` | e.g. `gpt-4o-mini` |
| `temperature` | Keep low (0.1) for reviews |
| `max_tokens` | Cap completion size |
| `timeout_seconds` | HTTP timeout |

If `OPENAI_API_KEY` is unset, provider falls back to null; **heuristics still run**.

---

## `memory`

| Key | Purpose |
|-----|---------|
| `enabled` | `true` / `false` |
| `backend` | `sqlite` or `postgres` |
| `path` | SQLite file path (relative to cwd) |
| `url` | Postgres SQLAlchemy URL when backend is postgres |

SQLite example:

```yaml
memory:
  enabled: true
  backend: sqlite
  path: .qgate/memory.db
```

Postgres example (production):

```yaml
memory:
  enabled: true
  backend: postgres
  url: postgresql+psycopg://qgate:${DB_PASSWORD}@db:5432/qgate
```

---

## `reporting`

| Key | Purpose |
|-----|---------|
| `formats` | `json`, `markdown`, `html` |
| `output_dir` | Directory created if missing |

---

## `repository.ignore_patterns`

Paths skipped during repository discovery (not a security boundary for the test runner; the runner also rejects paths outside the repo root).
