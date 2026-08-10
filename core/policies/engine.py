"""Deterministic Quality Policy Engine.

The LLM never makes the final PASS/BLOCK decision alone.
This engine enforces configurable rules.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from core.models.decision import DecisionType, GateDecision, ValidationPlan
from core.models.findings import Finding, FindingCategory, FindingSeverity, FindingStatus
from core.models.scoring import QualityScoreBreakdown, RiskScoreBreakdown
from core.policies.config import QGateConfig, QualityGateRules


class PolicyResult(BaseModel):
    decision: DecisionType
    reason: str
    blocking_findings: list[Finding] = Field(default_factory=list)
    warnings: list[Finding] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class PolicyEngine:
    """Applies deterministic quality gate rules."""

    def __init__(self, config: QGateConfig | None = None) -> None:
        self.config = config or QGateConfig()
        self.rules: QualityGateRules = self.config.quality_gate

    def evaluate(
        self,
        quality_score: float,
        risk_score: float,
        confidence: float,
        findings: list[Finding],
        test_results: dict[str, Any] | None = None,
        validation_plan: ValidationPlan | None = None,
        changed_files_count: int = 0,
        quality_breakdown: QualityScoreBreakdown | None = None,
        risk_breakdown: RiskScoreBreakdown | None = None,
    ) -> GateDecision:
        """Evaluate all inputs and produce a GateDecision."""
        test_results = test_results or {}
        blocking: list[Finding] = []
        warnings: list[Finding] = []
        recommendations: list[str] = []

        # 1. Collect blocking findings by severity / category
        for f in findings:
            if f.status in {FindingStatus.FALSE_POSITIVE, FindingStatus.IGNORED, FindingStatus.RESOLVED}:
                continue
            if self._is_blocking_finding(f):
                blocking.append(f)
            elif f.severity in {FindingSeverity.MEDIUM, FindingSeverity.HIGH}:
                warnings.append(f)
            elif f.severity == FindingSeverity.LOW:
                warnings.append(f)

        # 2. Test failures
        tests_failed = int(test_results.get("failed", 0) or 0)
        tests_passed = int(test_results.get("passed", 0) or 0)
        tests_executed = int(test_results.get("executed", tests_passed + tests_failed) or 0)
        if tests_failed > 0 and "targeted_test_failure" in self.rules.block_on:
            # Create synthetic finding if not already present
            if not any(f.category == FindingCategory.TEST and f.severity == FindingSeverity.CRITICAL for f in blocking):
                blocking.append(
                    Finding(
                        category=FindingCategory.TEST,
                        severity=FindingSeverity.CRITICAL,
                        title=f"{tests_failed} targeted test(s) failed",
                        description="One or more selected tests failed during validation.",
                        evidence=[f"failed={tests_failed}", f"passed={tests_passed}"],
                        confidence=1.0,
                        recommendation="Investigate failing tests before merging.",
                        source_agent="policy_engine",
                    )
                )

        # 3. Score thresholds
        if quality_score < self.rules.minimum_quality_score:
            blocking.append(
                Finding(
                    category=FindingCategory.CODE_QUALITY,
                    severity=FindingSeverity.HIGH,
                    title="Quality score below threshold",
                    description=f"Quality score {quality_score:.1f} < minimum {self.rules.minimum_quality_score}",
                    confidence=1.0,
                    recommendation="Improve code quality, tests, or address findings.",
                    source_agent="policy_engine",
                )
            )

        if risk_score > self.rules.maximum_risk_score:
            # High risk alone does not always block if no critical findings;
            # treat as warning unless configured strictly.
            if risk_score >= 80:
                blocking.append(
                    Finding(
                        category=FindingCategory.REGRESSION,
                        severity=FindingSeverity.HIGH,
                        title="Risk score critically high",
                        description=f"Risk score {risk_score:.1f} exceeds safe threshold.",
                        confidence=1.0,
                        recommendation="Reduce change scope or add more targeted validation.",
                        source_agent="policy_engine",
                    )
                )
            else:
                warnings.append(
                    Finding(
                        category=FindingCategory.REGRESSION,
                        severity=FindingSeverity.MEDIUM,
                        title="Elevated risk score",
                        description=f"Risk score {risk_score:.1f} > maximum preferred {self.rules.maximum_risk_score}",
                        confidence=1.0,
                        recommendation="Consider additional review or tests.",
                        source_agent="policy_engine",
                    )
                )

        # 4. Decide
        if blocking:
            decision = DecisionType.BLOCK
            reason = self._build_block_reason(blocking)
        elif warnings:
            decision = DecisionType.PASS_WITH_WARNINGS
            reason = f"Passed with {len(warnings)} warning(s)."
        else:
            decision = DecisionType.PASS
            reason = "All quality gate checks passed."

        # 5. Recommendations
        for f in blocking + warnings:
            if f.recommendation and f.recommendation not in recommendations:
                recommendations.append(f.recommendation)

        return GateDecision(
            decision=decision,
            quality_score=quality_score,
            risk_score=risk_score,
            confidence=confidence,
            quality_breakdown=quality_breakdown,
            risk_breakdown=risk_breakdown,
            blocking_findings=blocking,
            warnings=warnings,
            recommendations=recommendations,
            final_reason=reason,
            validation_plan=validation_plan,
            tests_required=len((validation_plan.unit_tests if validation_plan else []) or [])
            + len((validation_plan.integration_tests if validation_plan else []) or [])
            + len((validation_plan.e2e_tests if validation_plan else []) or []),
            tests_executed=tests_executed,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            changed_files_count=changed_files_count,
        )

    def _is_blocking_finding(self, f: Finding) -> bool:
        block_on = set(self.rules.block_on)

        if f.severity == FindingSeverity.CRITICAL:
            return True

        if f.category == FindingCategory.SECURITY:
            if "critical_security" in block_on and f.severity in {
                FindingSeverity.CRITICAL,
                FindingSeverity.HIGH,
            }:
                return True
            if "secret_detected" in block_on and "secret" in f.title.lower():
                return True

        if f.category == FindingCategory.REGRESSION and "critical_regression" in block_on:
            if f.severity in {FindingSeverity.CRITICAL, FindingSeverity.HIGH}:
                return True

        if f.category == FindingCategory.TEST and "targeted_test_failure" in block_on:
            if f.severity in {FindingSeverity.CRITICAL, FindingSeverity.HIGH}:
                return True

        return False

    def _build_block_reason(self, blocking: list[Finding]) -> str:
        titles = [f.title for f in blocking[:5]]
        extra = f" (+{len(blocking) - 5} more)" if len(blocking) > 5 else ""
        return "Blocked due to: " + "; ".join(titles) + extra
