"""Quality score calculator."""

from __future__ import annotations

from typing import Any

from core.models.findings import Finding, FindingCategory, FindingSeverity
from core.models.scoring import QualityScoreBreakdown
from core.policies.config import QGateConfig, ScoringWeights


class QualityScorer:
    """Computes a transparent quality score from findings and metrics."""

    def __init__(self, config: QGateConfig | None = None) -> None:
        self.config = config or QGateConfig()
        self.weights: ScoringWeights = self.config.scoring_weights

    def compute(
        self,
        findings: list[Finding],
        test_results: dict[str, Any] | None = None,
        confidence: float = 0.9,
        extra: dict[str, float] | None = None,
    ) -> QualityScoreBreakdown:
        test_results = test_results or {}
        extra = extra or {}

        # Start from perfect and subtract penalties
        code_quality = 100.0 - self._penalty_for_category(findings, FindingCategory.CODE_QUALITY)
        security = 100.0 - self._penalty_for_category(findings, FindingCategory.SECURITY)
        architecture = 100.0 - self._penalty_for_category(findings, FindingCategory.ARCHITECTURE)
        dependency = 100.0 - self._penalty_for_category(findings, FindingCategory.DEPENDENCY)
        regression = 100.0 - self._penalty_for_category(findings, FindingCategory.REGRESSION)

        # Test health from results
        executed = int(test_results.get("executed", 0) or 0)
        failed = int(test_results.get("failed", 0) or 0)
        if executed > 0:
            pass_rate = (executed - failed) / executed
            test_health = pass_rate * 100.0
            if failed > 0:
                test_health = max(0.0, test_health - failed * 10)
        else:
            # No tests run — mild penalty if we expected tests
            test_health = extra.get("test_health", 85.0)

        ai_confidence = confidence * 100.0

        # Apply optional overrides
        code_quality = extra.get("code_quality", code_quality)
        security = extra.get("security", security)
        architecture = extra.get("architecture", architecture)
        dependency = extra.get("dependency_health", dependency)
        regression = extra.get("regression_risk", regression)
        test_health = extra.get("test_health", test_health)

        # Clamp
        dims = {
            "code_quality": max(0.0, min(100.0, code_quality)),
            "test_health": max(0.0, min(100.0, test_health)),
            "security": max(0.0, min(100.0, security)),
            "regression_risk": max(0.0, min(100.0, regression)),
            "architecture": max(0.0, min(100.0, architecture)),
            "dependency_health": max(0.0, min(100.0, dependency)),
            "ai_confidence": max(0.0, min(100.0, ai_confidence)),
        }

        w = self.weights
        overall = (
            dims["code_quality"] * w.code_quality
            + dims["test_health"] * w.test_health
            + dims["security"] * w.security
            + dims["regression_risk"] * w.regression_risk
            + dims["architecture"] * w.architecture
            + dims["dependency_health"] * w.dependency_health
            + dims["ai_confidence"] * w.ai_confidence
        )

        explanation = (
            f"Weighted average of dimension scores. "
            f"Weights: CQ={w.code_quality}, TH={w.test_health}, SEC={w.security}, "
            f"RR={w.regression_risk}, ARCH={w.architecture}, DEP={w.dependency_health}, "
            f"AI={w.ai_confidence}."
        )

        return QualityScoreBreakdown(
            overall=round(overall, 1),
            code_quality=round(dims["code_quality"], 1),
            test_health=round(dims["test_health"], 1),
            security=round(dims["security"], 1),
            regression_risk=round(dims["regression_risk"], 1),
            architecture=round(dims["architecture"], 1),
            dependency_health=round(dims["dependency_health"], 1),
            ai_confidence=round(dims["ai_confidence"], 1),
            weights={
                "code_quality": w.code_quality,
                "test_health": w.test_health,
                "security": w.security,
                "regression_risk": w.regression_risk,
                "architecture": w.architecture,
                "dependency_health": w.dependency_health,
                "ai_confidence": w.ai_confidence,
            },
            explanation=explanation,
        )

    def _penalty_for_category(self, findings: list[Finding], category: FindingCategory) -> float:
        penalty = 0.0
        for f in findings:
            if f.category != category:
                continue
            if f.severity == FindingSeverity.CRITICAL:
                penalty += 40
            elif f.severity == FindingSeverity.HIGH:
                penalty += 20
            elif f.severity == FindingSeverity.MEDIUM:
                penalty += 8
            elif f.severity == FindingSeverity.LOW:
                penalty += 3
        return min(100.0, penalty)
