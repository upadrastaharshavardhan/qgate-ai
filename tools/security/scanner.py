"""Deterministic security scanner for changed files.

Does NOT rely exclusively on LLM. Uses pattern matching and optional
external tools (bandit) when available.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from core.models.findings import Finding, FindingCategory, FindingSeverity

logger = logging.getLogger(__name__)

# High-confidence secret patterns
SECRET_PATTERNS: list[tuple[str, re.Pattern[str], FindingSeverity]] = [
    (
        "Hardcoded password assignment",
        re.compile(
            r"""(?i)(password|passwd|pwd)\s*=\s*['"][^'"]{4,}['"]""",
        ),
        FindingSeverity.CRITICAL,
    ),
    (
        "Hardcoded API key / token",
        re.compile(
            r"""(?i)(api[_-]?key|apikey|secret[_-]?key|access[_-]?token|auth[_-]?token)\s*=\s*['"][A-Za-z0-9_\-]{12,}['"]""",
        ),
        FindingSeverity.CRITICAL,
    ),
    (
        "AWS access key id",
        re.compile(r"AKIA[0-9A-Z]{16}"),
        FindingSeverity.CRITICAL,
    ),
    (
        "Private key block",
        re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        FindingSeverity.CRITICAL,
    ),
    (
        "Generic secret assignment",
        re.compile(
            r"""(?i)(secret|token|credential)\s*=\s*['"][^'"]{8,}['"]""",
        ),
        FindingSeverity.HIGH,
    ),
]

# Code security anti-patterns
CODE_PATTERNS: list[tuple[str, re.Pattern[str], FindingSeverity, str]] = [
    (
        "Possible SQL injection (string format in query)",
        re.compile(r"""(?i)(execute|cursor\.execute|raw)\s*\(\s*[f'"].*%|.*\.format\("""),
        FindingSeverity.HIGH,
        "Use parameterized queries instead of string formatting.",
    ),
    (
        "Possible command injection",
        re.compile(r"""(?i)(os\.system|subprocess\.(call|run|Popen))\s*\([^)]*(f['"]|\.format\(|%\s*)"""),
        FindingSeverity.HIGH,
        "Avoid shell=True and untrusted input in subprocess calls.",
    ),
    (
        "eval() usage",
        re.compile(r"""\beval\s*\("""),
        FindingSeverity.HIGH,
        "Avoid eval() on untrusted input.",
    ),
    (
        "pickle.loads on untrusted data",
        re.compile(r"""pickle\.loads?\s*\("""),
        FindingSeverity.MEDIUM,
        "Prefer safer serialization; never unpickle untrusted data.",
    ),
    (
        "Disabled TLS verification",
        re.compile(r"""(?i)(verify\s*=\s*False|ssl\._create_unverified_context)"""),
        FindingSeverity.MEDIUM,
        "Do not disable TLS certificate verification in production.",
    ),
    (
        "Hardcoded localhost credentials in URL",
        re.compile(r"""(?i)(mysql|postgres|mongodb)://[^:]+:[^@]+@"""),
        FindingSeverity.HIGH,
        "Move credentials to environment variables or a secret store.",
    ),
]

# Test/fixture false-positive hints
TEST_PATH_MARKERS = ("test_", "tests/", "fixtures/", "conftest", "mock", "sample", "example")


class SecurityScanner:
    """Scan file contents for secrets and common vulnerabilities."""

    def __init__(self, repository_path: str | Path) -> None:
        self.root = Path(repository_path).resolve()

    def scan_files(self, file_paths: list[str], max_file_size: int = 200_000) -> list[Finding]:
        findings: list[Finding] = []
        for rel in file_paths:
            path = self.root / rel
            if not path.is_file():
                continue
            # Skip binary-ish extensions
            if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".pyc", ".so"}:
                continue
            try:
                if path.stat().st_size > max_file_size:
                    continue
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError as e:
                logger.debug("Cannot read %s: %s", rel, e)
                continue

            is_test = any(m in rel.lower() for m in TEST_PATH_MARKERS)
            findings.extend(self._scan_content(rel, content, is_test=is_test))

        # Optional bandit for Python
        py_files = [f for f in file_paths if f.endswith(".py")]
        if py_files:
            findings.extend(self._run_bandit(py_files))

        return findings

    def _scan_content(self, path: str, content: str, *, is_test: bool) -> list[Finding]:
        findings: list[Finding] = []
        lines = content.splitlines()

        for title, pattern, severity in SECRET_PATTERNS:
            for i, line in enumerate(lines, start=1):
                if pattern.search(line):
                    # Soften severity in tests
                    sev = severity
                    if is_test and severity == FindingSeverity.CRITICAL:
                        sev = FindingSeverity.MEDIUM
                    findings.append(
                        Finding(
                            category=FindingCategory.SECURITY,
                            severity=sev,
                            title=title,
                            description=f"{path}:{i} — {line.strip()[:120]}",
                            evidence=[f"{path}:{i}", line.strip()[:200]],
                            confidence=0.92 if not is_test else 0.7,
                            impacted_files=[path],
                            recommendation="Remove hardcoded secrets; use env vars or a secret manager.",
                            source_agent="security_scanner",
                            metadata={"line": i, "is_test_path": is_test},
                        )
                    )

        for title, pattern, severity, rec in CODE_PATTERNS:
            for i, line in enumerate(lines, start=1):
                if pattern.search(line):
                    findings.append(
                        Finding(
                            category=FindingCategory.SECURITY,
                            severity=severity,
                            title=title,
                            description=f"{path}:{i} — {line.strip()[:120]}",
                            evidence=[f"{path}:{i}", line.strip()[:200]],
                            confidence=0.75,
                            impacted_files=[path],
                            recommendation=rec,
                            source_agent="security_scanner",
                            metadata={"line": i},
                        )
                    )
        return findings

    def _run_bandit(self, py_files: list[str]) -> list[Finding]:
        """Optional Bandit integration; silent if not installed."""
        try:
            import bandit  # noqa: F401
            from bandit.core import manager as bandit_manager
            from bandit.core import config as bandit_config
        except ImportError:
            return []

        findings: list[Finding] = []
        try:
            conf = bandit_config.BanditConfig()
            mgr = bandit_manager.BanditManager(conf, "file")
            targets = [str(self.root / f) for f in py_files if (self.root / f).exists()]
            if not targets:
                return []
            mgr.discover_files(targets, recursive=False)
            mgr.run_tests()
            severity_map = {
                "HIGH": FindingSeverity.HIGH,
                "MEDIUM": FindingSeverity.MEDIUM,
                "LOW": FindingSeverity.LOW,
            }
            for issue in mgr.get_issue_list():
                sev = severity_map.get(str(issue.severity).upper(), FindingSeverity.MEDIUM)
                fname = str(issue.fname)
                try:
                    rel = str(Path(fname).relative_to(self.root))
                except ValueError:
                    rel = fname
                findings.append(
                    Finding(
                        category=FindingCategory.SECURITY,
                        severity=sev,
                        title=f"Bandit: {issue.test_id} — {issue.text[:80]}",
                        description=issue.text,
                        evidence=[f"{rel}:{issue.lineno}"],
                        confidence=0.85,
                        impacted_files=[rel],
                        recommendation="Review and remediate the Bandit finding.",
                        source_agent="bandit",
                        metadata={"test_id": issue.test_id, "line": issue.lineno},
                    )
                )
        except Exception as e:
            logger.debug("Bandit scan skipped/failed: %s", e)
        return findings
