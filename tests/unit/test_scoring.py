"""Unit tests for scorers."""

from core.models.findings import Finding, FindingCategory, FindingSeverity
from core.scoring.quality import QualityScorer
from core.scoring.risk import RiskScorer


def test_quality_perfect():
    scorer = QualityScorer()
    bd = scorer.compute(findings=[], confidence=1.0)
    assert bd.overall >= 95


def test_quality_penalty_critical():
    scorer = QualityScorer()
    findings = [
        Finding(
            category=FindingCategory.SECURITY,
            severity=FindingSeverity.CRITICAL,
            title="Secret",
            description="x",
            confidence=1.0,
        )
    ]
    bd = scorer.compute(findings=findings, confidence=0.9)
    assert bd.security < 70
    assert bd.overall < 95


def test_risk_low_for_small_change():
    scorer = RiskScorer()
    bd = scorer.compute(changed_files_count=1, total_additions=5, total_deletions=0)
    assert bd.overall < 30
    assert bd.level == "LOW"


def test_risk_high_for_large_critical():
    scorer = RiskScorer()
    bd = scorer.compute(
        changed_files_count=30,
        total_additions=800,
        total_deletions=200,
        has_critical_files=True,
        dependency_changes=2,
    )
    assert bd.overall > 25
    assert bd.level in ("MEDIUM", "HIGH", "VERY_HIGH", "CRITICAL")
    assert bd.change_size >= 80
