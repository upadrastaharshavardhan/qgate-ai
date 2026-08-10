"""Dependency Intelligence Agent."""

from __future__ import annotations

import logging
import time
from typing import Any

from core.state.quality_gate_state import QualityGateState
from tools.dependency.analyzer import DependencyAnalyzer

logger = logging.getLogger(__name__)


def dependency_analysis_node(state: QualityGateState) -> dict[str, Any]:
    start = time.perf_counter()
    config = state.get("config") or {}
    analysis = config.get("analysis") or {}
    if analysis.get("dependencies") is False:
        return {"dependency_findings": [], "phase": "dependency_skipped"}

    analyzer = DependencyAnalyzer(state["repository_path"])
    findings = analyzer.analyze_changed_files(
        changed_files=state.get("changed_files") or [],
        diff_summary=state.get("git_diff_summary") or "",
    )

    audit = list(state.get("audit_events") or [])
    audit.append(
        {
            "event": "dependency_analysis",
            "findings": len(findings),
            "duration_s": round(time.perf_counter() - start, 3),
        }
    )
    timeline = dict(state.get("execution_timeline") or {})
    timeline["dependency_analysis"] = round(time.perf_counter() - start, 3)

    return {
        "dependency_findings": [f.model_dump() for f in findings],
        "audit_events": audit,
        "execution_timeline": timeline,
        "phase": "dependency_analysis",
    }
