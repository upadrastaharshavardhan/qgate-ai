# Q-GATE AI Documentation

| Document | Contents |
|----------|----------|
| [PIPELINE_INTEGRATION.md](./PIPELINE_INTEGRATION.md) | **How to connect Q-GATE to GitHub Actions, GitLab CI, Azure DevOps, Jenkins, and local pre-push** — exit codes, secrets, caching, branch protection, troubleshooting |
| [CONFIGURATION.md](./CONFIGURATION.md) | Full `qgate.yaml` reference |

## Ready-to-copy pipeline files

| Platform | File in this repo |
|----------|-------------------|
| GitHub Actions | `integrations/github/qgate.yml` → copy to `.github/workflows/qgate.yml` |
| GitLab CI | `integrations/gitlab/.gitlab-ci-qgate.yml` |
| Azure DevOps | `integrations/azure_devops/azure-pipelines-qgate.yml` |
| Jenkins | `integrations/jenkins/Jenkinsfile` |

## One-command local check (real git repo)

```bash
pip install -e .
export PYTHONPATH=.
git fetch origin main
qgate check --base origin/main --head HEAD
```

Exit `0` = PASS / PASS_WITH_WARNINGS · Exit `1` = BLOCK · Exit `3` = tool error.

Reports: `.qgate/reports/qgate-report.{json,md,html}`
