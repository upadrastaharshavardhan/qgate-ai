"""Quality Policy + Scoring nodes (Phase 1 foundation)."""

from __future__ import annotations

import logging
import time
from typing import Any

from core.models.findings import Finding
from core.policies.config import QGateConfig, load_config
from core.policies.engine import PolicyEngine
from core.scoring.quality import QualityScorer
from core.scoring.risk import RiskScorer
from core.state.quality_gate_state import QualityGateState

logger = logging.getLogger(__name__)


def _collect_findings(state: QualityGateState) -> list[Finding]:
    findings: list[Finding] = []
    for key in (
        "quality_findings",
        "security_findings",
        "architecture_findings",
        "dependency_findings",
        "regression_findings",
        "ai_review_findings",
        "historical_findings",
    ):
        for raw in state.get(key) or []:
            try:
                findings.append(Finding.model_validate(raw))
            except Exception:
                continue
    return findings


def risk_and_quality_scoring_node(state: QualityGateState) -> dict[str, Any]:
    """Compute risk and quality scores from current state (Phase 1)."""
    start = time.perf_counter()
    config_data = state.get("config") or {}
    config = QGateConfig.model_validate(config_data) if config_data else load_config()

    findings = _collect_findings(state)
    change = state.get("change_summary") or {}
    changed_count = len(state.get("changed_files") or [])
    additions = int(change.get("total_additions") or 0)
    deletions = int(change.get("total_deletions") or 0)
    symbols = len(state.get("changed_symbols") or [])

    # Critical file heuristic
    critical_patterns = ("auth", "payment", "security", "password", "token", "secret", "admin")
    has_critical = any(
        any(p in f.lower() for p in critical_patterns) for f in (state.get("changed_files") or [])
    )

    risk_scorer = RiskScorer(config)
    risk_bd = risk_scorer.compute(
        changed_files_count=changed_count,
        total_additions=additions,
        total_deletions=deletions,
        changed_symbols_count=symbols,
        findings=findings,
        historical_context=state.get("historical_context") or {},
        has_critical_files=has_critical,
        dependency_changes=len(state.get("dependency_findings") or []),
    )

    quality_scorer = QualityScorer(config)
    quality_bd = quality_scorer.compute(
        findings=findings,
        test_results=state.get("test_results") or {},
        confidence=0.85,  # Phase 1 baseline
    )

    audit = list(state.get("audit_events") or [])
    audit.append(
        {
            "event": "scoring",
            "quality": quality_bd.overall,
            "risk": risk_bd.overall,
            "duration_s": round(time.perf_counter() - start, 3),
        }
    )
    timeline = dict(state.get("execution_timeline") or {})
    timeline["scoring"] = round(time.perf_counter() - start, 3)

    return {
        "quality_score": quality_bd.overall,
        "risk_score": risk_bd.overall,
        "confidence_score": quality_bd.ai_confidence / 100.0,
        "quality_breakdown": quality_bd.model_dump(),
        "risk_breakdown": risk_bd.model_dump(),
        "audit_events": audit,
        "execution_timeline": timeline,
        "phase": "scoring",
    }


def quality_policy_node(state: QualityGateState) -> dict[str, Any]:
    """Apply deterministic policy engine to produce final decision."""
    start = time.perf_counter()
    config_data = state.get("config") or {}
    config = QGateConfig.model_validate(config_data) if config_data else load_config()

    findings = _collect_findings(state)
    engine = PolicyEngine(config)

    from core.models.decision import ValidationPlan
    from core.models.scoring import QualityScoreBreakdown, RiskScoreBreakdown

    q_bd = None
    r_bd = None
    if state.get("quality_breakdown"):
        q_bd = QualityScoreBreakdown.model_validate(state["quality_breakdown"])
    if state.get("risk_breakdown"):
        r_bd = RiskScoreBreakdown.model_validate(state["risk_breakdown"])

    plan = None
    if state.get("validation_plan"):
        try:
            plan = ValidationPlan.model_validate(state["validation_plan"])
        except Exception:
            plan = None

    decision = engine.evaluate(
        quality_score=float(state.get("quality_score") or 100),
        risk_score=float(state.get("risk_score") or 0),
        confidence=float(state.get("confidence_score") or 0.8),
        findings=findings,
        test_results=state.get("test_results") or {},
        validation_plan=plan,
        changed_files_count=len(state.get("changed_files") or []),
        quality_breakdown=q_bd,
        risk_breakdown=r_bd,
    )

    audit = list(state.get("audit_events") or [])
    audit.append(
        {
            "event": "quality_policy",
            "decision": decision.decision.value,
            "blocking": len(decision.blocking_findings),
            "warnings": len(decision.warnings),
            "duration_s": round(time.perf_counter() - start, 3),
        }
    )
    timeline = dict(state.get("execution_timeline") or {})
    timeline["quality_policy"] = round(time.perf_counter() - start, 3)

    return {
        "final_decision": decision.decision.value,
        "final_reason": decision.final_reason,
        "gate_decision": decision.model_dump(),
        "blocking_findings": [f.model_dump() for f in decision.blocking_findings],
        "warnings": [f.model_dump() for f in decision.warnings],
        "recommendations": decision.recommendations,
        "audit_events": audit,
        "execution_timeline": timeline,
        "phase": "decision",
    }
