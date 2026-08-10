"""Detect dependency file changes and basic risk signals."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from core.models.findings import Finding, FindingCategory, FindingSeverity

logger = logging.getLogger(__name__)

DEP_FILE_NAMES = {
    "requirements.txt",
    "pyproject.toml",
    "Pipfile",
    "Pipfile.lock",
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "go.mod",
    "go.sum",
    "Cargo.toml",
    "Cargo.lock",
    "Gemfile",
    "Gemfile.lock",
    "composer.json",
    "composer.lock",
}

# Known high-risk package name patterns (illustrative)
HIGH_RISK_PACKAGES = {
    "django",
    "flask",
    "fastapi",
    "express",
    "react",
    "next",
    "spring-boot",
    "openssl",
    "cryptography",
    "requests",
    "urllib3",
    "lodash",
    "jquery",
}


class DependencyAnalyzer:
    def __init__(self, repository_path: str | Path) -> None:
        self.root = Path(repository_path).resolve()

    def analyze_changed_files(self, changed_files: list[str], diff_summary: str = "") -> list[Finding]:
        findings: list[Finding] = []
        dep_changes = [f for f in changed_files if Path(f).name in DEP_FILE_NAMES]

        if not dep_changes:
            return findings

        findings.append(
            Finding(
                category=FindingCategory.DEPENDENCY,
                severity=FindingSeverity.MEDIUM,
                title=f"Dependency manifest(s) changed ({len(dep_changes)})",
                description="Dependency files were modified: " + ", ".join(dep_changes),
                evidence=dep_changes,
                confidence=1.0,
                impacted_files=dep_changes,
                recommendation="Review version bumps for breaking changes and known CVEs.",
                source_agent="dependency_analyzer",
            )
        )

        for rel in dep_changes:
            path = self.root / rel
            if not path.is_file():
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            name = Path(rel).name
            if name == "package.json":
                findings.extend(self._analyze_package_json(rel, content))
            elif name in ("requirements.txt", "Pipfile"):
                findings.extend(self._analyze_requirements(rel, content))
            elif name == "pyproject.toml":
                findings.extend(self._analyze_pyproject(rel, content))

        # Diff-based: look for version bumps of high-risk packages
        if diff_summary:
            findings.extend(self._scan_diff_for_risk(diff_summary, dep_changes))

        return findings

    def _analyze_package_json(self, path: str, content: str) -> list[Finding]:
        findings: list[Finding] = []
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return findings
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        for pkg in deps:
            if pkg.lower() in HIGH_RISK_PACKAGES:
                findings.append(
                    Finding(
                        category=FindingCategory.DEPENDENCY,
                        severity=FindingSeverity.LOW,
                        title=f"Critical-path dependency present: {pkg}",
                        description=f"{pkg}@{deps[pkg]} is in the dependency tree.",
                        evidence=[path, f"{pkg}={deps[pkg]}"],
                        confidence=0.8,
                        impacted_files=[path],
                        recommendation="Ensure upgrades are intentional and tested.",
                        source_agent="dependency_analyzer",
                    )
                )
        return findings

    def _analyze_requirements(self, path: str, content: str) -> list[Finding]:
        findings: list[Finding] = []
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r"^([A-Za-z0-9_\-]+)", line)
            if m and m.group(1).lower() in HIGH_RISK_PACKAGES:
                findings.append(
                    Finding(
                        category=FindingCategory.DEPENDENCY,
                        severity=FindingSeverity.LOW,
                        title=f"Critical-path dependency: {m.group(1)}",
                        description=line[:120],
                        evidence=[path, line],
                        confidence=0.8,
                        impacted_files=[path],
                        recommendation="Review version constraints carefully.",
                        source_agent="dependency_analyzer",
                    )
                )
        return findings

    def _analyze_pyproject(self, path: str, content: str) -> list[Finding]:
        # Lightweight: flag if dependencies section exists and file changed
        if "[project.dependencies]" in content or "dependencies" in content:
            return [
                Finding(
                    category=FindingCategory.DEPENDENCY,
                    severity=FindingSeverity.LOW,
                    title="pyproject.toml dependencies section present",
                    description="Python project dependencies may have changed.",
                    evidence=[path],
                    confidence=0.7,
                    impacted_files=[path],
                    recommendation="Diff pyproject.toml carefully for version ranges.",
                    source_agent="dependency_analyzer",
                )
            ]
        return []

    def _scan_diff_for_risk(self, diff: str, dep_files: list[str]) -> list[Finding]:
        findings: list[Finding] = []
        # Lines that look like version upgrades of high-risk packages
        for pkg in HIGH_RISK_PACKAGES:
            # +package==x or "package": "x"
            if re.search(rf"[\+\-].*{re.escape(pkg)}", diff, re.IGNORECASE):
                findings.append(
                    Finding(
                        category=FindingCategory.DEPENDENCY,
                        severity=FindingSeverity.MEDIUM,
                        title=f"Version change involving high-impact package: {pkg}",
                        description=f"Diff mentions {pkg} in a dependency file change.",
                        evidence=dep_files[:5],
                        confidence=0.85,
                        impacted_files=dep_files,
                        recommendation=f"Run tests covering {pkg} usage; check changelog/CVEs.",
                        source_agent="dependency_analyzer",
                    )
                )
        return findings
