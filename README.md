# Q-GATE AI

<img width="287" height="188" alt="image" src="https://github.com/user-attachments/assets/33f0c51d-1793-41b6-a9d2-bb0c2347777f" />


### AI-Powered Quality Gate for Every Git Change

**Don’t let bad code reach the branch.**

Q-GATE AI is a **LangGraph-powered autonomous quality gate** that analyzes every code change, understands its impact, evaluates security and regression risk, selects the most relevant tests, executes them, investigates failures, and makes a deterministic **PASS / WARN / BLOCK** decision before code reaches your protected branch.

It works against the **real repository** — real Git history, real file contents, real test processes, and real historical quality data.

> **Think of Q-GATE AI as an intelligent quality-control layer between a your code change and your Git branch.**

---

## 🚀 Why Q-GATE AI?

Traditional CI pipelines usually answer:

> **"Did the tests pass?"**

Q-GATE AI asks a much larger set of questions:

* What actually changed?
* Which parts of the application are affected?
* Is the change security-sensitive?
* Did dependencies change?
* Which tests are actually relevant?
* What is the historical risk of these files?
* Are critical paths affected?
* Are tests missing for the change?
* Did the failure come from the code, test, environment, or infrastructure?
* Should this change **PASS, WARN, or BLOCK**?

Instead of blindly running everything, Q-GATE AI builds a **change-aware quality decision**.

---

# 🧠 The Core Idea

```text
                         ┌─────────────────────┐
                         │     Git Change      │
                         │    base → HEAD      │
                         └──────────┬──────────┘
                                    │
                                    ▼
                       ┌────────────────────────┐
                       │ Repository Intelligence│
                       │ language / framework   │
                       │ structure / tests      │
                       └───────────┬────────────┘
                                   │
                                   ▼
                       ┌────────────────────────┐
                       │    Change Analysis     │
                       │ files / diff / stats   │
                       │ symbols / dependencies │
                       └───────────┬────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
              ▼                    ▼                    ▼
      ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
      │   Security   │     │  Test Impact │     │ Regression   │
      │ Intelligence │     │   Analysis   │     │    Risk      │
      └──────┬───────┘     └──────┬───────┘     └──────┬───────┘
             │                    │                    │
             └────────────────────┼────────────────────┘
                                  ▼
                       ┌────────────────────────┐
                       │ Historical Intelligence│
                       │ hotspots / failures    │
                       │ previous decisions     │
                       └───────────┬────────────┘
                                   │
                                   ▼
                       ┌────────────────────────┐
                       │ Validation Planner     │
                       │ Select relevant tests  │
                       └───────────┬────────────┘
                                   │
                                   ▼
                       ┌────────────────────────┐
                       │ Real Test Execution    │
                       │ pytest / Playwright /  │
                       │ application tests      │
                       └───────────┬────────────┘
                                   │
                         ┌─────────┴─────────┐
                         │                   │
                         ▼                   ▼
                  Tests Passed         Tests Failed
                         │                   │
                         │                   ▼
                         │          ┌─────────────────┐
                         │          │ Failure         │
                         │          │ Investigator    │
                         │          └────────┬────────┘
                         │                   │
                         └─────────┬─────────┘
                                   ▼
                       ┌────────────────────────┐
                       │ Quality + Risk Engine  │
                       └───────────┬────────────┘
                                   │
                                   ▼
                       ┌────────────────────────┐
                       │    POLICY ENGINE       │
                       │                        │
                       │  🟢 PASS               │
                       │  🟡 PASS_WITH_WARNINGS │
                       │  🔴 BLOCK              │
                       └───────────┬────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
             Quality Memory                 CI/CD Result
             JSON / MD / HTML               Exit Code
```

---
<img width="1983" height="793" alt="image" src="https://github.com/user-attachments/assets/20063718-96b6-4e3a-aedc-df571fc37b0a" />


---
# ⚡ What Makes It Different?

| Traditional Quality Gate    | Q-GATE AI                           |
| --------------------------- | ----------------------------------- |
| Runs predefined checks      | Understands the change first        |
| Usually runs all tests      | Selects relevant tests              |
| Test result = decision      | Risk + quality + policy = decision  |
| Limited historical context  | Learns from quality history         |
| Failure = red pipeline      | Investigates failure cause          |
| Static rules                | Intelligence + deterministic policy |
| Generic CI output           | Explainable quality report          |
| Treats every file similarly | Identifies risky / critical areas   |
| Mostly reactive             | Change-aware and predictive         |

---

# 🔍 What Happens When a Developer Pushes Code?

Suppose a developer changes:

```text
src/payment/payment_service.py
```

Q-GATE AI doesn't simply execute the entire test suite.

It investigates:

```text
1. What changed?
        ↓
2. Which symbols/functions changed?
        ↓
3. Is this payment-critical functionality?
        ↓
4. Did authentication/security logic change?
        ↓
5. Which tests cover this area?
        ↓
6. Has this file historically caused failures?
        ↓
7. Are there dependency changes?
        ↓
8. What is the regression risk?
        ↓
9. Which tests should actually run?
        ↓
10. Did those tests pass?
        ↓
11. If they failed, why?
        ↓
12. Should the branch be allowed?
```

The final decision is not simply:

```text
Tests = PASS
```

It becomes:

```text
Quality Score: 91
Risk Score: 24

Security:       PASS
Dependencies:   PASS
Test Impact:    PASS
Regression:     LOW
Targeted Tests: PASS
Historical Risk: LOW

Decision: PASS
```

---

# 🏗️ Architecture

Q-GATE AI is built around **LangGraph** to model quality analysis as a stateful, conditional workflow.

```text
                         Q-GATE AI
                             │
                             ▼
                    ┌─────────────────┐
                    │   State Graph   │
                    │    LangGraph    │
                    └────────┬────────┘
                             │
             ┌───────────────┼────────────────┐
             │               │                │
             ▼               ▼                ▼
       Repository       Change Analysis    Intelligence
       Discovery                           Agents
             │               │                │
             │               │       ┌────────┼────────┐
             │               │       │        │        │
             ▼               ▼       ▼        ▼        ▼
         Git Engine       AST/Diff Security Dependencies
                                         │
                                         ▼
                                   Test Impact
                                         │
                                         ▼
                                  Regression Risk
                                         │
                                         ▼
                                  Historical Memory
                                         │
             └───────────────┬───────────────┘
                             ▼
                    Validation Planner
                             │
                             ▼
                       Test Runner
                             │
                     ┌───────┴────────┐
                     ▼                ▼
                  SUCCESS           FAILURE
                     │                │
                     │                ▼
                     │        Failure Investigator
                     │                │
                     └───────┬────────┘
                             ▼
                       Scoring Engine
                             │
                             ▼
                       Policy Engine
                             │
                 ┌───────────┼───────────┐
                 ▼           ▼           ▼
               PASS         WARN        BLOCK
                             │
                             ▼
                       Quality Memory
```

---

# 🤖 Intelligence Layer

Q-GATE AI combines multiple specialized quality-analysis capabilities.

## 🔐 Security Intelligence

Detects security-sensitive changes such as:

* Potential secrets
* Credential exposure
* Injection patterns
* Security-sensitive code changes
* Dangerous patterns
* Optional Bandit analysis

---

## 📦 Dependency Intelligence

Analyzes:

* `requirements.txt`
* `pyproject.toml`
* `package.json`
* Dependency modifications
* Potentially affected application areas

---

## 🧠 AI Code Review

Performs change-focused code analysis.

When `OPENAI_API_KEY` is configured, Q-GATE AI can optionally use an LLM for deeper review.

Without an API key, the quality gate still works using deterministic analysis and heuristics.

**AI is optional. The quality gate is not.**

---

## 🎯 Test Impact Analysis

Instead of blindly running every test:

```text
10,000 tests
      ↓
Changed files
      ↓
Changed symbols
      ↓
Affected functionality
      ↓
Relevant tests
      ↓
Targeted validation
```

Tests are categorized using priority levels:

```text
P0 → Critical
P1 → High
P2 → Medium
P3 → Low
```

This creates a foundation for faster and more intelligent CI validation.

---

# 📈 Regression Risk Intelligence

Q-GATE AI evaluates risk using signals such as:

* Critical-path changes
* Historical failures
* Frequently changed files
* Previous block decisions
* Missing tests
* Security-sensitive changes
* Dependency changes
* Test impact
* Change characteristics

Example:

```text
┌───────────────────────────────────┐
│        REGRESSION RISK            │
├───────────────────────────────────┤
│ Critical Path        ████████  HIGH│
│ Historical Failures  ████     MED │
│ Change Size          ███      MED │
│ Test Coverage        ███████  HIGH│
│ Dependency Change    ██       LOW │
├───────────────────────────────────┤
│ Final Risk Score: 68 / 100        │
└───────────────────────────────────┘
```

---

# 🧬 Quality Memory

Q-GATE AI does not have to treat every commit as an isolated event.

Historical quality information can be persisted in:

```text
.qgate/memory.db
```

The memory layer can track signals such as:

* Previous quality decisions
* Historical failures
* Problematic files
* Quality hotspots
* Failure patterns
* Block rates
* Previous test outcomes

Over time:

```text
Commit 1 ──┐
Commit 2 ──┤
Commit 3 ──┤
Commit 4 ──┼──► Quality Memory
Commit 5 ──┤
Commit 6 ──┘
                  │
                  ▼
          Historical Intelligence
```

This enables Q-GATE AI to ask:

> "Has this area of the codebase caused problems before?"

---

# 🧪 Real Test Execution

Q-GATE AI does not simulate test execution.

It launches real processes against the target repository.

Currently supported execution includes:

```text
pytest
Playwright
```

The architecture is designed to support additional test runners.

Example:

```bash
qgate check --base origin/main --head HEAD
```

Q-GATE AI can:

```text
Analyze change
     ↓
Build validation plan
     ↓
Select tests
     ↓
Execute tests
     ↓
Capture output
     ↓
Investigate failures
     ↓
Calculate risk
     ↓
Apply policy
```

---

# 🔎 Failure Investigation

A failed test does not automatically mean:

```text
BLOCK
```

Q-GATE AI investigates the failure context.

Possible categories include:

```text
CODE_FAILURE
TEST_FAILURE
ENVIRONMENT_FAILURE
INFRASTRUCTURE_FAILURE
DEPENDENCY_FAILURE
UNKNOWN
```

This helps separate:

> "The application is broken"

from:

> "The test environment is broken."

That distinction is critical for CI/CD quality gates.

---

# ⚖️ Deterministic Policy Engine

AI can provide intelligence.

But **AI should not have unrestricted authority over production branch protection.**

Q-GATE AI therefore separates:

```text
AI / Intelligence
        ↓
Scores + Findings + Evidence
        ↓
Deterministic Policy
        ↓
Final Decision
```

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
```

Possible outcomes:

### 🟢 PASS

The change satisfies the configured quality policy.

### 🟡 PASS_WITH_WARNINGS

The change is allowed, but quality concerns should be reviewed.

### 🔴 BLOCK

The change violates a mandatory quality policy.

---

# 🚦 CI/CD Exit Codes

Q-GATE AI integrates naturally with CI/CD systems.

| Exit Code | Meaning                   | Pipeline |
| --------: | ------------------------- | -------- |
|       `0` | PASS / PASS_WITH_WARNINGS | Continue |
|       `1` | BLOCK                     | Fail     |
|       `2` | Configuration error       | Fail     |
|       `3` | Tool/runtime error        | Fail     |

This makes Q-GATE AI easy to integrate with branch protection.

---

# 🔄 End-to-End Quality Lifecycle

```text
Developer
   │
   │ git push
   ▼
CI Pipeline
   │
   ▼
Q-GATE AI
   │
   ├── Discover repository
   ├── Analyze Git diff
   ├── Understand changed symbols
   ├── Scan security
   ├── Analyze dependencies
   ├── Review code
   ├── Calculate test impact
   ├── Calculate regression risk
   ├── Query historical memory
   │
   ▼
Validation Planner
   │
   ▼
Targeted Test Execution
   │
   ├── PASS ───────────────┐
   │                       │
   └── FAIL → Investigator │
                           │
                           ▼
                    Quality + Risk
                           │
                           ▼
                    Policy Engine
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
            PASS          WARN        BLOCK
              │            │            │
              └────────────┼────────────┘
                           ▼
                    Quality Report
                           │
                           ▼
                    Quality Memory
```

---

# 📊 Reports

Every Q-GATE AI execution produces machine-readable and human-readable reports.

```text
.qgate/
├── reports/
│   ├── qgate-report.json
│   ├── qgate-report.md
│   └── qgate-report.html
│
└── memory.db
```

### JSON

Designed for:

* CI/CD integrations
* Dashboards
* APIs
* Automation
* Machine processing

### Markdown

Designed for:

* Pull requests
* Developer review
* CI logs
* Human-readable summaries

### HTML

Designed for:

* Detailed investigation
* Local review
* Quality reporting

---

# 🔌 CI/CD Integrations

Q-GATE AI can be integrated with:

* GitHub Actions
* GitLab CI
* Azure DevOps
* Jenkins
* Pre-push Git hooks

Ready-to-use templates are included:

```text
integrations/
├── github/
│   └── qgate.yml
│
├── gitlab/
│   └── .gitlab-ci-qgate.yml
│
├── azure_devops/
│   └── azure-pipelines-qgate.yml
│
└── jenkins/
    └── Jenkinsfile
```

---

# 🚀 Quick Start

## 1. Clone Q-GATE AI

```bash
git clone <repository-url>
cd qgate-ai
```

## 2. Create the environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

Windows:

```powershell
.venv\Scripts\activate
```

## 3. Install

```bash
pip install -e ".[dev]"
```

## 4. Configure Python path

```bash
export PYTHONPATH=.
```

Windows:

```powershell
$env:PYTHONPATH="."
```

## 5. Initialize the project

From the application repository:

```bash
qgate init
```

This creates:

```text
qgate.yaml
```

## 6. Run the quality gate

```bash
qgate check --base origin/main --head HEAD
```

Or explicitly specify the target repository:

```bash
python -m apps.cli.main check \
  --base origin/main \
  --head HEAD \
  --path /absolute/path/to/app
```

---

# ⚙️ Configuration

Create `qgate.yaml` in the application repository.

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

memory:
  enabled: true
  backend: sqlite
  path: .qgate/memory.db
```

For the complete configuration reference:

```text
docs/CONFIGURATION.md
```

---

# 🧠 Optional LLM Intelligence

Set:

```bash
export OPENAI_API_KEY=your-key
```

The LLM layer is optional.

Without it, Q-GATE AI still performs:

```text
✓ Git analysis
✓ Repository discovery
✓ Security analysis
✓ Dependency analysis
✓ Test impact analysis
✓ Regression analysis
✓ Test execution
✓ Failure investigation
✓ Quality scoring
✓ Policy enforcement
✓ Historical memory
✓ Reporting
```

This design ensures that **AI augmentation does not become a single point of failure for CI/CD.**

---

# 🖥️ CLI

```bash
qgate init
```

Initialize a repository with a configuration file.

```bash
qgate check --base origin/main --head HEAD
```

Analyze and validate a change.

```bash
qgate report
```

Show the latest generated reports.

```bash
qgate memory-stats
```

Display quality-memory statistics.

```bash
qgate suppress <fingerprint> --status false_positive
```

Suppress a known false positive.

```bash
qgate version
```

Display the installed version.

---

# 🔗 Pipeline Integration

The general integration pattern is:

```bash
git fetch origin <target-branch> --depth=50

pip install -e .

# Install application dependencies
pip install -r requirements.txt

# Run Q-GATE
qgate check \
  --base origin/<target-branch> \
  --head <commit-sha>
```

For Node-based applications, install the application dependencies first:

```bash
npm ci
```

The important principle is:

```text
Application dependencies
        +
Q-GATE AI
        +
Targeted tests
        ↓
Quality decision
```

---

# 📚 Documentation

| Document                                                       | Purpose                          |
| -------------------------------------------------------------- | -------------------------------- |
| [`docs/README.md`](docs/README.md)                             | Documentation index              |
| [`docs/PIPELINE_INTEGRATION.md`](docs/PIPELINE_INTEGRATION.md) | CI/CD integration                |
| [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md)               | Complete configuration reference |

---

# 🧪 Testing Q-GATE AI

Run the unit test suite:

```bash
export PYTHONPATH=.
pytest tests/unit -q
```

The test suite covers:

```text
✓ Policy engine
✓ Quality scoring
✓ Security scanner
✓ Test impact analysis
✓ Test runner
✓ Failure investigator
✓ Memory store
```

Tests operate against temporary real filesystems and real subprocess execution where appropriate.

---

# 🗺️ Roadmap

| Phase       | Capability                                                                  | Status     |
| ----------- | --------------------------------------------------------------------------- | ---------- |
| **Phase 1** | LangGraph state, Git analysis, discovery, scoring, policy, CLI, reports     | ✅ Done     |
| **Phase 2** | Security, dependency, code review, test impact, regression, parallel agents | ✅ Done     |
| **Phase 3** | Validation planner, test runner, failure investigator, conditional workflow | ✅ Done     |
| **Phase 4** | SQLite quality memory, historical intelligence, Playwright runner           | ✅ Done     |
| **Phase 5** | React quality dashboard                                                     | 🚧 Planned |
| **Phase 6** | Packaged CI adapters beyond YAML templates                                  | 🚧 Planned |

### Future direction

```text
              TODAY                         FUTURE
                │                             │
                ▼                             ▼
         Change Analysis              Continuous Learning
                │                             │
                ▼                             ▼
         Risk Prediction              Organization-wide Memory
                │                             │
                ▼                             ▼
          Test Selection              Predictive Quality
                │                             │
                ▼                             ▼
         Test Execution              Autonomous Validation
                │                             │
                ▼                             ▼
        PASS / WARN / BLOCK          Intelligent Quality Platform
```

---

# 🎯 Design Principles

Q-GATE AI is built around a few important principles.

### 1. Real Repository, Real Evidence

No fake repository context.

Analysis happens against the actual repository specified by `--path`.

### 2. AI-Assisted, Policy-Controlled

AI can recommend and analyze.

The deterministic policy engine makes the final branch decision.

### 3. Change-Aware Testing

Do not waste CI resources blindly running everything when targeted validation can provide meaningful confidence.

### 4. Explainable Decisions

A quality gate should tell developers **why** it blocked their change.

### 5. Historical Intelligence

Previous failures and quality patterns should become useful context for future changes.

### 6. CI/CD First

Q-GATE AI is designed to work as an automated quality gate inside existing engineering pipelines.

---

# 🏆 The Vision

Most CI systems operate like this:

```text
Code
 ↓
Build
 ↓
Run tests
 ↓
PASS / FAIL
```

Q-GATE AI aims for:

```text
Code Change
     ↓
Understand
     ↓
Assess Impact
     ↓
Assess Security
     ↓
Predict Risk
     ↓
Remember History
     ↓
Select Validation
     ↓
Execute Tests
     ↓
Investigate Failures
     ↓
Score Quality
     ↓
Apply Policy
     ↓
Explain Decision
     ↓
PASS / WARN / BLOCK
```

The goal is not to replace your existing CI pipeline.

The goal is to make your CI pipeline **understand the change before deciding whether it is safe.**

---

# 🛡️ Q-GATE AI

### **Understand the change.**

### **Predict the risk.**

### **Validate what matters.**

### **Block what shouldn't ship.**

---
<img width="864" height="1821" alt="image" src="https://github.com/user-attachments/assets/230d9d41-c88c-489e-bcfe-2c5abad72e6c" />



---

## License

MIT
