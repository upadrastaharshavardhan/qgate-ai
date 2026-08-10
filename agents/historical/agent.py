"""Historical Intelligence + Memory Persist agents."""

from __future__ import annotations

import logging
import time
from typing import Any

from core.memory.store import get_memory_store
from core.models.findings import Finding, FindingCategory, FindingSeverity, FindingStatus
from core.state.quality_gate_state import QualityGateState

logger = logging.getLogger(__name__)


def historical_intelligence_node(state: QualityGateState) -> dict[str, Any]:
    """Load repository memory and produce historical findings."""
    start = time.perf_counter()
    config = state.get("config") or {}
    analysis = config.get("analysis") or {}
    if analysis.get("historical_analysis") is False:
        return {"historical_context": {}, "historical_findings": [], "phase": "historical_skipped"}

    store = get_memory_store(config)
    if store is None:
        return {
            "historical_context": {"enabled": False},
            "historical_findings": [],
            "phase": "historical_skipped",
        }

    changed = state.get("changed_files") or []
    ctx = store.get_historical_context(state["repository_path"], changed_files=changed)
    ctx["enabled"] = True

    findings: list[Finding] = []

    # Hotspot warnings
    for hs in ctx.get("hotspots") or []:
        if hs.get("failure_count", 0) >= 2 or hs.get("block_count", 0) >= 1:
            findings.append(
                Finding(
                    category=FindingCategory.HISTORICAL,
                    severity=FindingSeverity.HIGH
                    if hs.get("block_count", 0) >= 2
                    else FindingSeverity.MEDIUM,
                    title=f"Historical hotspot: {hs['file_path']}",
                    description=(
                        f"File changed {hs.get('change_count', 0)} times, "
                        f"{hs.get('failure_count', 0)} related failures, "
                        f"{hs.get('block_count', 0)} prior blocks "
                        f"(avg risk {hs.get('risk_score_avg', 0)})."
                    ),
                    evidence=[str(hs)],
                    confidence=0.85,
                    impacted_files=[hs["file_path"]],
                    recommendation="Extra review and stronger tests for this hotspot.",
                    source_agent="historical_intelligence",
                )
            )

    # Similar past failures
    for sf in (ctx.get("similar_failures") or [])[:5]:
        findings.append(
            Finding(
                category=FindingCategory.HISTORICAL,
                severity=FindingSeverity.MEDIUM,
                title=f"Similar past failure: {sf.get('test_nodeid')}",
                description=f"Previously classified as {sf.get('classification')} on {sf.get('commit')}",
                evidence=[str(sf)],
                confidence=0.7,
                recommendation="Ensure this test is included in targeted validation.",
                source_agent="historical_intelligence",
            )
        )

    # Elevate risk context for scorer
    if ctx.get("failure_rate", 0) >= 0.4:
        findings.append(
            Finding(
                category=FindingCategory.HISTORICAL,
                severity=FindingSeverity.MEDIUM,
                title="Elevated historical block rate",
                description=f"Recent block rate is {ctx['failure_rate']:.0%} across {ctx.get('analysis_count', 0)} analyses.",
                evidence=[f"failure_rate={ctx['failure_rate']}"],
                confidence=0.9,
                recommendation="Tighten validation for this repository.",
                source_agent="historical_intelligence",
            )
        )

    # Suppress known false positives from current security/quality findings
    suppressed = {s["fingerprint"] for s in ctx.get("suppressed_findings") or []}
    # Annotate context for downstream agents
    ctx["suppressed_fingerprints"] = list(suppressed)

    # Self-improving test relevance
    relevance = store.get_test_relevance(state["repository_path"], changed)
    ctx["test_relevance"] = relevance

    # Boost tests_to_execute later via context; merge high-relevance tests
    boosted = list(state.get("tests_to_execute") or [])
    for nodeid, score in sorted(relevance.items(), key=lambda x: -x[1])[:10]:
        # nodeid may be file::test — prefer file path for runner
        path = nodeid.split("::")[0]
        if path and path not in boosted and score >= 0.1:
            boosted.append(path)

    audit = list(state.get("audit_events") or [])
    audit.append(
        {
            "event": "historical_intelligence",
            "analyses": ctx.get("analysis_count", 0),
            "hotspots": len(ctx.get("hotspots") or []),
            "findings": len(findings),
            "duration_s": round(time.perf_counter() - start, 3),
        }
    )
    timeline = dict(state.get("execution_timeline") or {})
    timeline["historical_intelligence"] = round(time.perf_counter() - start, 3)

    result: dict[str, Any] = {
        "historical_context": ctx,
        "historical_findings": [f.model_dump(mode="json") for f in findings],
        "audit_events": audit,
        "execution_timeline": timeline,
        "phase": "historical_intelligence",
    }
    if boosted != list(state.get("tests_to_execute") or []):
        result["tests_to_execute"] = boosted
    return result


def memory_persist_node(state: QualityGateState) -> dict[str, Any]:
    """Persist analysis, findings, and failures after the decision."""
    start = time.perf_counter()
    config = state.get("config") or {}
    store = get_memory_store(config)
    if store is None:
        return {"phase": "memory_persist_skipped"}

    decision = state.get("final_decision") or ""
    head = state.get("head_commit") or ""
    changed = state.get("changed_files") or []
    tr = state.get("test_results") or {}

    try:
        store.record_analysis(
            repository_path=state["repository_path"],
            base_commit=state.get("base_commit") or "",
            head_commit=head,
            decision=decision,
            quality_score=float(state.get("quality_score") or 0),
            risk_score=float(state.get("risk_score") or 0),
            confidence=float(state.get("confidence_score") or 0),
            changed_files=changed,
            tests_executed=int(tr.get("executed") or 0),
            tests_failed=int(tr.get("failed") or 0),
            final_reason=state.get("final_reason") or "",
            source_branch=state.get("source_branch") or "",
            target_branch=state.get("target_branch") or "",
            payload={
                "blocking": len(state.get("blocking_findings") or []),
                "warnings": len(state.get("warnings") or []),
            },
        )

        all_findings: list[dict[str, Any]] = []
        for key in (
            "security_findings",
            "quality_findings",
            "dependency_findings",
            "regression_findings",
            "ai_review_findings",
            "historical_findings",
            "blocking_findings",
            "warnings",
        ):
            all_findings.extend(state.get(key) or [])
        store.record_findings(
            repository_path=state["repository_path"],
            head_commit=head,
            findings=all_findings,
        )

        inv = (state.get("historical_context") or {}).get("failure_investigations") or []
        if inv:
            store.record_test_failures(
                repository_path=state["repository_path"],
                head_commit=head,
                investigations=inv,
            )
    except Exception as e:
        logger.exception("Memory persist failed: %s", e)
        return {
            "errors": list(state.get("errors") or []) + [f"memory_persist: {e}"],
            "phase": "memory_persist_error",
        }

    audit = list(state.get("audit_events") or [])
    audit.append(
        {
            "event": "memory_persist",
            "decision": decision,
            "duration_s": round(time.perf_counter() - start, 3),
        }
    )
    timeline = dict(state.get("execution_timeline") or {})
    timeline["memory_persist"] = round(time.perf_counter() - start, 3)

    return {
        "audit_events": audit,
        "execution_timeline": timeline,
        "phase": "memory_persist",
    }
