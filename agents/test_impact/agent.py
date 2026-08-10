"""Test Impact Analysis Agent — select P0/P1 tests without running full suite."""

from __future__ import annotations

import logging
import time
from typing import Any

from core.state.quality_gate_state import QualityGateState
from tools.testing.discovery import TestDiscoveryTool
from tools.testing.impact import TestImpactAnalyzer

logger = logging.getLogger(__name__)


def test_impact_analysis_node(state: QualityGateState) -> dict[str, Any]:
    start = time.perf_counter()
    config = state.get("config") or {}
    analysis = config.get("analysis") or {}
    if analysis.get("test_impact_analysis") is False:
        return {
            "impacted_tests": [],
            "candidate_tests": [],
            "tests_to_execute": [],
            "phase": "test_impact_skipped",
        }

    profile = state.get("repository_profile") or {}
    language = (profile.get("language") or {}).get("primary") or "python"
    test_dirs = profile.get("test_directories") or []
    source_dirs = profile.get("source_directories") or []

    discovery = TestDiscoveryTool(state["repository_path"])
    all_tests = discovery.discover(language=language, test_dirs=test_dirs)

    impact = TestImpactAnalyzer(state["repository_path"])
    result = impact.select(
        changed_files=state.get("changed_files") or [],
        all_tests=all_tests,
        changed_symbols=state.get("changed_symbols") or [],
        source_dirs=source_dirs,
    )

    audit = list(state.get("audit_events") or [])
    audit.append(
        {
            "event": "test_impact_analysis",
            "discovered": result["total_discovered"],
            "p0": len(result["p0"]),
            "p1": len(result["p1"]),
            "to_execute": len(result["tests_to_execute"]),
            "duration_s": round(time.perf_counter() - start, 3),
        }
    )
    timeline = dict(state.get("execution_timeline") or {})
    timeline["test_impact_analysis"] = round(time.perf_counter() - start, 3)

    logger.info(
        "Test impact: %d discovered, P0=%d P1=%d execute=%d",
        result["total_discovered"],
        len(result["p0"]),
        len(result["p1"]),
        len(result["tests_to_execute"]),
    )

    return {
        "impacted_tests": result["impacted_tests"],
        "candidate_tests": result["candidate_tests"],
        "tests_to_execute": result["tests_to_execute"],
        "validation_plan": {
            "static_analysis": True,
            "security_scan": True,
            "unit_tests": result["p0"][:30],
            "integration_tests": result["p1"][:20],
            "e2e_tests": [],
            "full_regression": False,
            "skip_tests": len(result["tests_to_execute"]) == 0,
            "reason": f"Selected {len(result['tests_to_execute'])} tests (P0+P1)",
        },
        "audit_events": audit,
        "execution_timeline": timeline,
        "phase": "test_impact_analysis",
    }
