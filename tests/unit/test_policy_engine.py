"""Unit tests for PolicyEngine."""

from core.models.findings import Finding, FindingCategory, FindingSeverity
from core.policies.config import QGateConfig, QualityGateRules
from core.policies.engine import PolicyEngine
from core.models.decision import DecisionType


def test_pass_when_clean():
    engine = PolicyEngine(QGateConfig())
    result = engine.evaluate(
        quality_score=95,
        risk_score=10,
        confidence=0.9,
        findings=[],
    )
    assert result.decision == DecisionType.PASS


def test_block_on_critical_security():
    engine = PolicyEngine(QGateConfig())
    findings = [
        Finding(
            category=FindingCategory.SECURITY,
            severity=FindingSeverity.CRITICAL,
            title="Hardcoded secret detected",
            description="password = 'secret123'",
            confidence=0.99,
        )
    ]
    result = engine.evaluate(quality_score=90, risk_score=20, confidence=0.9, findings=findings)
    assert result.decision == DecisionType.BLOCK
    assert len(result.blocking_findings) >= 1


def test_warning_on_medium():
    engine = PolicyEngine(QGateConfig())
    findings = [
        Finding(
            category=FindingCategory.CODE_QUALITY,
            severity=FindingSeverity.MEDIUM,
            title="High complexity",
            description="Function exceeds complexity threshold",
            confidence=0.8,
        )
    ]
    result = engine.evaluate(quality_score=88, risk_score=25, confidence=0.85, findings=findings)
    assert result.decision == DecisionType.PASS_WITH_WARNINGS


def test_block_on_low_quality_score():
    engine = PolicyEngine(
        QGateConfig(quality_gate=QualityGateRules(minimum_quality_score=80))
    )
    result = engine.evaluate(quality_score=50, risk_score=10, confidence=0.9, findings=[])
    assert result.decision == DecisionType.BLOCK
