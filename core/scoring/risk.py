"""Change risk score calculator."""

from __future__ import annotations

from typing import Any

from core.models.findings import Finding, FindingCategory, FindingSeverity
from core.models.scoring import RiskScoreBreakdown
from core.policies.config import QGateConfig, RiskWeights


class RiskScorer:
    """Computes an independent risk score (0–100, higher = riskier)."""

    def __init__(self, config: QGateConfig | None = None) -> None:
        self.config = config or QGateConfig()
        self.weights: RiskWeights = self.config.risk_weights

    def compute(
        self,
        changed_files_count: int = 0,
        total_additions: int = 0,
        total_deletions: int = 0,
        changed_symbols_count: int = 0,
        findings: list[Finding] | None = None,
        historical_context: dict[str, Any] | None = None,
        has_critical_files: bool = False,
        dependency_changes: int = 0,
        extra: dict[str, float] | None = None,
    ) -> RiskScoreBreakdown:
        findings = findings or []
        historical_context = historical_context or {}
        extra = extra or {}

        # Change size (files + lines)
        lines = total_additions + total_deletions
        size_score = min(100.0, changed_files_count * 4 + lines / 20)

        # Complexity proxy from symbols and findings
        complexity = min(100.0, changed_symbols_count * 5 + len(findings) * 3)

        # Criticality
        criticality = 30.0 if has_critical_files else 10.0
        if any(f.category == FindingCategory.SECURITY and f.severity in {FindingSeverity.CRITICAL, FindingSeverity.HIGH} for f in findings):
            criticality = max(criticality, 70.0)
        if any(f.category == FindingCategory.REGRESSION and f.severity == FindingSeverity.CRITICAL for f in findings):
            criticality = max(criticality, 80.0)

        # Historical
        hist_rate = float(historical_context.get("failure_rate", 0.0) or 0.0)
        historical = min(100.0, hist_rate * 100)

        # Coverage proxy (lack of tests increases risk)
        coverage_risk = float(historical_context.get("coverage_risk", 20.0) or 20.0)

        # Dependency impact
        dep_impact = min(100.0, dependency_changes * 25)

        # Security impact from findings
        sec_impact = 0.0
        for f in findings:
            if f.category == FindingCategory.SECURITY:
                if f.severity == FindingSeverity.CRITICAL:
                    sec_impact = max(sec_impact, 90)
                elif f.severity == FindingSeverity.HIGH:
                    sec_impact = max(sec_impact, 60)
                elif f.severity == FindingSeverity.MEDIUM:
                    sec_impact = max(sec_impact, 30)

        # Overrides
        size_score = extra.get("change_size", size_score)
        complexity = extra.get("complexity", complexity)
        criticality = extra.get("criticality", criticality)
        historical = extra.get("historical_failure", historical)
        coverage_risk = extra.get("test_coverage", coverage_risk)
        dep_impact = extra.get("dependency_impact", dep_impact)
        sec_impact = extra.get("security_impact", sec_impact)

        dims = {
            "change_size": max(0.0, min(100.0, size_score)),
            "complexity": max(0.0, min(100.0, complexity)),
            "criticality": max(0.0, min(100.0, criticality)),
            "historical_failure": max(0.0, min(100.0, historical)),
            "test_coverage": max(0.0, min(100.0, coverage_risk)),
            "dependency_impact": max(0.0, min(100.0, dep_impact)),
            "security_impact": max(0.0, min(100.0, sec_impact)),
        }

        w = self.weights
        overall = (
            dims["change_size"] * w.change_size
            + dims["complexity"] * w.complexity
            + dims["criticality"] * w.criticality
            + dims["historical_failure"] * w.historical_failure
            + dims["test_coverage"] * w.test_coverage
            + dims["dependency_impact"] * w.dependency_impact
            + dims["security_impact"] * w.security_impact
        )

        level = self._level(overall)

        return RiskScoreBreakdown(
            overall=round(overall, 1),
            change_size=round(dims["change_size"], 1),
            complexity=round(dims["complexity"], 1),
            criticality=round(dims["criticality"], 1),
            historical_failure=round(dims["historical_failure"], 1),
            test_coverage=round(dims["test_coverage"], 1),
            dependency_impact=round(dims["dependency_impact"], 1),
            security_impact=round(dims["security_impact"], 1),
            level=level,
            explanation=f"Risk level {level} based on weighted factors.",
        )

    def _level(self, score: float) -> str:
        if score <= 20:
            return "LOW"
        if score <= 40:
            return "MEDIUM"
        if score <= 60:
            return "HIGH"
        if score <= 80:
            return "VERY_HIGH"
        return "CRITICAL"
