# Q-GATE AI — Pipeline Integration Guide

This document explains **exactly** how to wire Q-GATE AI into real developer workflows and CI/CD systems.

No sample placeholders. Every command, exit code, path, and YAML block is production-usable.

---

## 1. What Q-GATE does in a pipeline

Q-GATE analyzes the **git diff** between two refs (typically the protected branch and the commit under test), then:

1. Discovers language / test framework / layout  
2. Scores risk and quality from security, dependencies, code review, history  
3. Selects **only relevant tests** (not the full suite by default)  
4. Runs those tests when required  
5. Classifies failures (real regression vs environment vs flaky)  
6. Applies a **deterministic policy engine**  
7. Writes JSON / Markdown / HTML reports  
8. Persists the run into quality memory  

**Final decision:**

| Decision | Meaning | Typical CI outcome |
|----------|---------|-------------------|
| `PASS` | Safe to merge | Job succeeds (exit `0`) |
| `PASS_WITH_WARNINGS` | Safe, but review warnings | Job succeeds (exit `0`) unless you choose otherwise |
| `BLOCK` | Must not merge | Job fails (exit `1`) |

### Process exit codes (use these in CI)

| Code | Meaning |
|------|---------|
| `0` | `PASS` or `PASS_WITH_WARNINGS` |
| `1` | `BLOCK` |
| `2` | Configuration error (missing repo, bad config) |
| `3` | Tool / runtime error (git failure, runner crash) |

CI systems treat non-zero as failure. That is intentional for `BLOCK`.

---

## 2. Core command used everywhere

```bash
qgate check --base <BASE_REF> --head <HEAD_REF> [--path <REPO>] [--config <qgate.yaml>]
```

### Choosing base and head (real rules)

| Context | `--base` | `--head` |
|---------|----------|----------|
| Local before push | `origin/main` (or `origin/master`) | `HEAD` |
| GitHub PR | `origin/<base_branch>` after fetch | `HEAD` (merge commit or PR head) |
| GitHub push to branch | `origin/main` | `GITHUB_SHA` |
| GitLab MR | `origin/$CI_MERGE_REQUEST_TARGET_BRANCH_NAME` | `$CI_COMMIT_SHA` |
| Azure DevOps PR | `origin/$(System.PullRequest.TargetBranchName)` | `$(Build.SourceVersion)` |
| Jenkins PR | `origin/${CHANGE_TARGET}` | `GIT_COMMIT` |

**Always fetch the base ref before comparing:**

```bash
git fetch origin main --depth=50
qgate check --base origin/main --head HEAD
```

If the base commit is missing locally, git diff fails and Q-GATE exits with a tool error (`3`).

---

## 3. Install in CI (real steps)

### Python environment

Requires **Python 3.12+**.

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
# or from a private index / wheel once you publish:
# pip install qgate-ai
```

From a monorepo checkout where the package lives at `./qgate-ai`:

```bash
cd qgate-ai
pip install -e .
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

If the CLI entry point is not on `PATH`, call the module:

```bash
python -m apps.cli.main check --base origin/main --head HEAD
```

### Optional: LLM review

Only needed if you want the optional AI code-review pass (heuristics always run without it):

```bash
export OPENAI_API_KEY="sk-..."   # GitHub secret / GitLab CI variable / ADO secret
```

Without the key, Q-GATE still runs: security, test impact, pytest/playwright, policy, memory.

### Optional: Bandit (Python security)

```bash
pip install bandit
```

---

## 4. Repository setup (once per application repo)

In the **application** repository (the one under test), not only in the qgate-ai source tree:

### 4.1 Add `qgate.yaml` at the repo root

Copy and adjust from this project’s `qgate.yaml`. Critical real settings:

```yaml
project:
  name: your-service-name

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

analysis:
  security: true
  dependencies: true
  historical_analysis: true
  test_impact_analysis: true
  ai_code_review: true   # uses OPENAI_API_KEY if set; otherwise heuristics only

execution:
  timeout_minutes: 30
  allowlist_commands:
    - pytest
    - python
    - npm
    - npx

memory:
  enabled: true
  backend: sqlite
  path: .qgate/memory.db
  # Production:
  # backend: postgres
  # url: postgresql+psycopg://qgate:${DB_PASSWORD}@db:5432/qgate

reporting:
  formats:
    - json
    - markdown
    - html
  output_dir: .qgate/reports
```

Commit `qgate.yaml` so every pipeline uses the same policy.

### 4.2 Cache quality memory (recommended)

SQLite memory grows with each run. Persist it between CI jobs so historical intelligence works:

- Cache path: `.qgate/memory.db`
- Key by repository name (not by commit SHA)

Without cache, every CI job starts with empty history (still correct, just less smart).

### 4.3 Artifacts to publish

After each run:

| Path | Purpose |
|------|---------|
| `.qgate/reports/qgate-report.json` | Machine-readable for dashboards / PR bots |
| `.qgate/reports/qgate-report.md` | Human summary for PR comments |
| `.qgate/reports/qgate-report.html` | Full HTML report |

---

## 5. Local developer workflow (pre-push)

### One-time

```bash
cd /path/to/your-app
# install qgate-ai once (editable or package)
pip install -e /path/to/qgate-ai

qgate init          # writes qgate.yaml if missing
```

### Before every push

```bash
git fetch origin main
qgate check --base origin/main --head HEAD
echo $?   # 0 = ok to push, 1 = fix before push
```

### Git pre-push hook (real)

Create `.git/hooks/pre-push` (executable):

```bash
#!/usr/bin/env bash
set -euo pipefail

remote="$1"
url="$2"

# Only gate pushes to the default remote; adjust as needed
z40=0000000000000000000000000000000000000000

while read -r local_ref local_sha remote_ref remote_sha
do
  if [[ "$local_sha" = "$z40" ]]; then
    continue   # delete
  fi
  if [[ "$remote_sha" = "$z40" ]]; then
    base="origin/main"
  else
    base="$remote_sha"
  fi
  echo "Q-GATE AI: checking $local_sha against $base"
  git fetch origin main --quiet || true
  qgate check --base "origin/main" --head "$local_sha" || exit 1
done

exit 0
```

```bash
chmod +x .git/hooks/pre-push
```

For team-wide hooks, use [pre-commit](https://pre-commit.com/) or a shared hook installer in onboarding docs.

---

## 6. GitHub Actions (real workflow)

File: `.github/workflows/qgate.yml` in the **application** repository.

```yaml
name: Q-GATE AI

on:
  pull_request:
    branches: [main, master, develop]
  push:
    branches: [main, master]

concurrency:
  group: qgate-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  quality-gate:
    runs-on: ubuntu-latest
    timeout-minutes: 45

    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0   # full history for accurate base comparison

      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - name: Install Q-GATE AI
        run: |
          # Option A: install from your published package
          # pip install qgate-ai

          # Option B: install from a git submodule / sibling path
          # pip install -e ./qgate-ai

          # Option C: install from private GitHub package
          pip install "qgate-ai @ git+https://github.com/YOUR_ORG/qgate-ai.git@main"

      - name: Cache quality memory
        uses: actions/cache@v4
        with:
          path: .qgate/memory.db
          key: qgate-memory-${{ github.repository }}
          restore-keys: |
            qgate-memory-${{ github.repository }}

      - name: Resolve base ref
        id: refs
        run: |
          if [ "${{ github.event_name }}" = "pull_request" ]; then
            echo "base=origin/${{ github.base_ref }}" >> "$GITHUB_OUTPUT"
            echo "head=HEAD" >> "$GITHUB_OUTPUT"
            git fetch origin "${{ github.base_ref }}" --depth=50
          else
            # push: compare against previous commit on same branch when possible
            echo "base=origin/${{ github.ref_name }}^" >> "$GITHUB_OUTPUT"
            echo "head=HEAD" >> "$GITHUB_OUTPUT"
            git fetch origin "${{ github.ref_name }}" --depth=50 || true
            # safer for main: compare last push range
            if [ "${{ github.ref_name }}" = "main" ] || [ "${{ github.ref_name }}" = "master" ]; then
              echo "base=${{ github.event.before }}" >> "$GITHUB_OUTPUT"
            fi
          fi

      - name: Run Q-GATE AI
        id: qgate
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          set +e
          qgate check \
            --base "${{ steps.refs.outputs.base }}" \
            --head "${{ steps.refs.outputs.head }}" \
            --config qgate.yaml
          code=$?
          set -e
          echo "exit_code=$code" >> "$GITHUB_OUTPUT"
          exit $code

      - name: Upload reports
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: qgate-reports
          path: |
            .qgate/reports/qgate-report.json
            .qgate/reports/qgate-report.md
            .qgate/reports/qgate-report.html
          if-no-files-found: warn

      - name: Comment PR with report summary
        if: always() && github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const path = '.qgate/reports/qgate-report.md';
            if (!fs.existsSync(path)) {
              console.log('No markdown report found');
              return;
            }
            const body = fs.readFileSync(path, 'utf8');
            const header = '## Q-GATE AI Report\n\n';
            await github.rest.issues.createComment({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.issue.number,
              body: header + body.slice(0, 60000)
            });
```

### Required GitHub secrets

| Secret | Required | Purpose |
|--------|----------|---------|
| `OPENAI_API_KEY` | No | Optional LLM code review |
| (none for core gate) | — | Security scan + targeted tests work without LLM |

### Branch protection

In GitHub → Settings → Branches → Branch protection rules for `main`:

1. Require status checks to pass  
2. Select the check name **`Q-GATE AI / quality-gate`** (job name from the workflow)  
3. Do not allow bypass for regular developers if you want a hard gate  

---

## 7. GitLab CI (real `.gitlab-ci.yml`)

```yaml
stages:
  - quality

qgate:
  stage: quality
  image: python:3.12-slim
  timeout: 45 minutes
  variables:
    PIP_CACHE_DIR: "$CI_PROJECT_DIR/.cache/pip"
  cache:
    key: qgate-${CI_PROJECT_PATH_SLUG}
    paths:
      - .cache/pip
      - .qgate/memory.db
  before_script:
    - apt-get update -qq && apt-get install -y -qq git
    - pip install --upgrade pip
    - pip install "qgate-ai @ git+https://gitlab.com/YOUR_GROUP/qgate-ai.git@main"
    # Ensure base branch is available
    - |
      if [ -n "$CI_MERGE_REQUEST_TARGET_BRANCH_NAME" ]; then
        git fetch origin "$CI_MERGE_REQUEST_TARGET_BRANCH_NAME" --depth=50
        export QGATE_BASE="origin/$CI_MERGE_REQUEST_TARGET_BRANCH_NAME"
      else
        git fetch origin "$CI_DEFAULT_BRANCH" --depth=50
        export QGATE_BASE="origin/$CI_DEFAULT_BRANCH"
      fi
  script:
    - qgate check --base "$QGATE_BASE" --head "$CI_COMMIT_SHA" --config qgate.yaml
  artifacts:
    when: always
    paths:
      - .qgate/reports/
    expire_in: 30 days
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
```

### GitLab CI/CD variables

| Variable | Type | Purpose |
|----------|------|---------|
| `OPENAI_API_KEY` | Masked | Optional LLM |
| (DB URL if Postgres memory) | Masked | `memory.url` |

Mark the job as a **required pipeline job** for protected branches under Settings → Merge requests → Merge checks.

---

## 8. Azure DevOps (real pipeline YAML)

File: `azure-pipelines-qgate.yml`

```yaml
trigger:
  branches:
    include:
      - main
      - master

pr:
  branches:
    include:
      - main
      - master

pool:
  vmImage: ubuntu-latest

variables:
  python.version: "3.12"

steps:
  - checkout: self
    fetchDepth: 0

  - task: UsePythonVersion@0
    inputs:
      versionSpec: "$(python.version)"

  - script: |
      python -m pip install --upgrade pip
      pip install "qgate-ai @ git+https://dev.azure.com/YOUR_ORG/YOUR_PROJECT/_git/qgate-ai?path=/&version=GBMain"
    displayName: Install Q-GATE AI

  - task: Cache@2
    inputs:
      key: 'qgate | "$(Agent.OS)" | $(Build.Repository.Name)'
      path: .qgate
    displayName: Cache quality memory and reports dir

  - script: |
      set -e
      if [ -n "$(System.PullRequest.TargetBranch)" ]; then
        TARGET="$(System.PullRequest.TargetBranch)"
        TARGET="${TARGET#refs/heads/}"
        git fetch origin "$TARGET" --depth=50
        BASE="origin/$TARGET"
      else
        git fetch origin main --depth=50 || git fetch origin master --depth=50
        BASE="origin/main"
      fi
      qgate check --base "$BASE" --head "$(Build.SourceVersion)" --config qgate.yaml
    displayName: Run Q-GATE AI
    env:
      OPENAI_API_KEY: $(OPENAI_API_KEY)

  - task: PublishPipelineArtifact@1
    condition: always()
    inputs:
      targetPath: .qgate/reports
      artifact: qgate-reports
```

Store `OPENAI_API_KEY` as a secret variable in the pipeline or variable group.

Add this pipeline as a required check on the PR policy for the target branch.

---

## 9. Jenkins (real Declarative Pipeline)

```groovy
pipeline {
  agent any
  options {
    timeout(time: 45, unit: 'MINUTES')
    timestamps()
  }
  environment {
    OPENAI_API_KEY = credentials('openai-api-key') // optional Jenkins credential id
  }
  stages {
    stage('Checkout') {
      steps {
        checkout scm
        sh 'git fetch --all --depth=50 || true'
      }
    }
    stage('Install Q-GATE') {
      steps {
        sh '''
          python3.12 -m venv .venv
          . .venv/bin/activate
          pip install -U pip
          pip install "qgate-ai @ git+https://github.com/YOUR_ORG/qgate-ai.git@main"
        '''
      }
    }
    stage('Q-GATE check') {
      steps {
        sh '''
          . .venv/bin/activate
          if [ -n "${CHANGE_TARGET:-}" ]; then
            git fetch origin "${CHANGE_TARGET}" --depth=50
            BASE="origin/${CHANGE_TARGET}"
          else
            git fetch origin main --depth=50
            BASE="origin/main"
          fi
          qgate check --base "$BASE" --head "${GIT_COMMIT}" --config qgate.yaml
        '''
      }
    }
  }
  post {
    always {
      archiveArtifacts artifacts: '.qgate/reports/**', allowEmptyArchive: true
    }
  }
}
```

Configure the job as a required status check in your GitHub/Bitbucket branch protection if Jenkins reports back via the Git plugin.

---

## 10. How the pipeline should interpret reports

### JSON (`qgate-report.json`) — automation

Key fields after a real run:

```json
{
  "decision": {
    "decision": "BLOCK",
    "quality_score": 67.0,
    "risk_score": 20.0,
    "confidence": 0.85,
    "final_reason": "Blocked due to: ...",
    "blocking_findings": [ ... ],
    "warnings": [ ... ],
    "tests_executed": 1,
    "tests_failed": 1
  }
}
```

Use this for:

- Custom dashboards  
- Slack/Teams notifications  
- Auto-labeling PRs (`qgate:blocked`, `qgate:warnings`)

### Markdown / HTML — humans

Post `qgate-report.md` on the PR. Open `qgate-report.html` from artifacts for the full view.

---

## 11. Mapping Q-GATE to pipeline stages (recommended layout)

Do **not** replace your entire CI with Q-GATE. Place it as an early, smart gate:

```text
PR opened / push
    │
    ├─ 1. Q-GATE AI          ← diff-aware; targeted tests; BLOCK/PASS
    │
    ├─ 2. Full build         ← compile / docker build (still required)
    │
    ├─ 3. Full test suite    ← nightly or high-risk only (Q-GATE can request full_regression)
    │
    └─ 4. Deploy / release
```

Policy in `qgate.yaml`:

- Low risk change → Q-GATE runs a **small** targeted set → faster PR feedback  
- High risk / many files → `require_full_regression_when` expands selection  

Your existing full suite job can stay as a separate required check on `main`, or run nightly.

---

## 12. Playwright projects in CI

When the repo uses Playwright, Q-GATE selects `playwright` as the runner if the framework is detected (`playwright` in package.json / config).

CI must provide browsers:

```yaml
# GitHub Actions example addition
- name: Install Playwright browsers
  run: npx playwright install --with-deps chromium
```

Ensure `npx` is on the allowlist (default in `qgate.yaml`).

Timeouts: set `execution.timeout_minutes` high enough for e2e (e.g. `45`).

---

## 13. Security and secrets in pipelines

| Rule | Detail |
|------|--------|
| Never log `OPENAI_API_KEY` | Use platform secret stores only |
| Q-GATE does not print secrets from code as “values to use” | Findings show path/line evidence; fix by rotating real leaked credentials |
| Test commands are allowlisted | LLM cannot invent shell commands |
| Memory DB may contain failure messages | Treat `.qgate/memory.db` as internal; do not publish publicly |

If a secret is found in the diff, decision is **BLOCK** when `secret_detected` / `critical_security` is in `block_on`.

---

## 14. Troubleshooting real pipeline failures

| Symptom | Cause | Fix |
|---------|--------|-----|
| Exit code 3, “Not a git repository” | Checkout without `.git` | Use full checkout (`fetch-depth: 0` or non-shallow) |
| Exit code 3, cannot resolve base | Base branch not fetched | `git fetch origin main` before `qgate check` |
| Always PASS with 0 tests | Diff is docs-only or no matching tests | Expected for pure markdown; add tests when source changes |
| BLOCK on tests, “ModuleNotFoundError” | CI missing app dependencies | Install app `requirements.txt` / `npm ci` **before** `qgate check` |
| Empty memory every run | Cache path not restored | Cache `.qgate/memory.db` with a stable key |
| Playwright not found | Browsers not installed | `npx playwright install --with-deps` |
| LLM review never runs | No API key | Set `OPENAI_API_KEY`; heuristics still apply |

Install **application** dependencies before Q-GATE when tests import application code:

```bash
pip install -r requirements.txt    # or poetry install / npm ci
qgate check --base origin/main --head HEAD
```

---

## 15. Minimal “first green pipeline” checklist

1. [ ] `qgate.yaml` committed at app repo root  
2. [ ] Python 3.12 on the runner  
3. [ ] `qgate-ai` installed in the job  
4. [ ] `git fetch` of the target branch before check  
5. [ ] App test dependencies installed before check  
6. [ ] `qgate check --base … --head …` is the gate step  
7. [ ] Non-zero exit fails the job  
8. [ ] Reports uploaded as artifacts  
9. [ ] Branch protection requires this check  
10. [ ] (Optional) Memory DB cached  
11. [ ] (Optional) `OPENAI_API_KEY` secret for LLM review  

---

## 16. Command reference for operators

```bash
# Analyze current branch vs main
qgate check --base origin/main --head HEAD

# Explicit config
qgate check --base origin/main --head HEAD --config ./qgate.yaml

# Another work tree
qgate check --base origin/main --head HEAD --path /home/runner/work/app/app

# After a run
qgate report
qgate memory-stats --path .

# Suppress a known false positive (fingerprint from report/memory)
qgate suppress <fingerprint> --status false_positive
```

---

## 17. What is real vs what is not

| Item | Status in this codebase |
|------|-------------------------|
| Git diff analysis | Real (GitPython) |
| Security patterns / optional Bandit | Real |
| Pytest targeted execution | Real |
| Playwright runner invocation | Real (needs browsers in environment) |
| Failure classification | Real heuristics |
| Policy PASS/BLOCK | Real deterministic rules |
| SQLite quality memory | Real |
| GitHub/GitLab/ADO/Jenkins YAML | Real templates in this guide and under `integrations/` |
| React dashboard | Not built yet (Phase 5) |
| Managed multi-tenant SaaS | Not built yet |

You can connect Q-GATE to pipelines **today** with the steps above. The gate decision and reports are produced from the actual repository under test—not from dummy data.

---

## 18. Related files in this repository

| Path | Purpose |
|------|---------|
| `qgate.yaml` | Default policy/config |
| `apps/cli/main.py` | CLI entry (`qgate`) |
| `graphs/main_graph.py` | Full LangGraph workflow |
| `integrations/github/` | Copy-paste workflow files |
| `integrations/gitlab/` | GitLab CI fragment |
| `integrations/azure_devops/` | Azure pipeline fragment |
| `integrations/jenkins/` | Jenkinsfile fragment |
| `docs/PIPELINE_INTEGRATION.md` | This document |
