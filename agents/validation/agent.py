"""Validation Planner + Test Execution agents."""

from __future__ import annotations

import logging
import time
from typing import Any

from core.models.decision import ValidationPlan
from core.state.quality_gate_state import QualityGateState
from tools.testing.runner import TestRunner

logger = logging.getLogger(__name__)


def validation_planner_node(state: QualityGateState) -> dict[str, Any]:
    """Refine validation plan from risk, findings, and test impact."""
    start = time.perf_counter()
    config = state.get("config") or {}
    qg = config.get("quality_gate") or {}
    require_full = qg.get("require_full_regression_when") or {}

    existing = state.get("validation_plan") or {}
    risk = float(state.get("risk_score") or 0)
    changed_count = len(state.get("changed_files") or [])
    tests_to_run = list(state.get("tests_to_execute") or [])

    # Security critical → still run selected tests (don't skip)
    security_findings = state.get("security_findings") or []
    has_critical_sec = any(
        (f.get("severity") == "critical") for f in security_findings
    )

    full_regression = False
    if risk >= float(require_full.get("risk_score") or 75):
        full_regression = True
    if changed_count >= int(require_full.get("changed_files") or 25):
        full_regression = True

    # If full regression requested but we only have candidates, expand to candidates
    if full_regression:
        candidates = state.get("candidate_tests") or tests_to_run
        tests_to_run = list(dict.fromkeys(candidates or tests_to_run))

    # Skip execution if only docs/config changed and no tests selected
    skip = False
    changed = state.get("changed_files") or []
    code_like = [
        f
        for f in changed
        if not f.endswith((".md", ".txt", ".rst", ".yml", ".yaml", ".json", ".lock", ".toml"))
        and "qgate.yaml" not in f
    ]
    if not tests_to_run and not code_like:
        skip = True

    # Don't bother running tests if already blocked by critical secrets?
    # Policy can still want test evidence — we run unless skip.
    plan = ValidationPlan(
        static_analysis=True,
        security_scan=True,
        unit_tests=tests_to_run[:40],
        integration_tests=list(existing.get("integration_tests") or [])[:20],
        e2e_tests=list(existing.get("e2e_tests") or [])[:10],
        full_regression=full_regression,
        skip_tests=skip,
        reason=(
            "Skipped: non-code change"
            if skip
            else (
                f"Full regression requested (risk={risk:.0f}, files={changed_count})"
                if full_regression
                else f"Targeted: {len(tests_to_run)} tests"
            )
        ),
    )

    audit = list(state.get("audit_events") or [])
    audit.append(
        {
            "event": "validation_planner",
            "tests": len(plan.unit_tests),
            "skip": plan.skip_tests,
            "full_regression": plan.full_regression,
            "duration_s": round(time.perf_counter() - start, 3),
        }
    )
    timeline = dict(state.get("execution_timeline") or {})
    timeline["validation_planner"] = round(time.perf_counter() - start, 3)

    return {
        "validation_plan": plan.model_dump(),
        "tests_to_execute": plan.unit_tests if not plan.skip_tests else [],
        "audit_events": audit,
        "execution_timeline": timeline,
        "phase": "validation_planner",
        # Stash for routing
        "_skip_tests": plan.skip_tests,
        "_has_critical_security": has_critical_sec,
    }


def test_execution_node(state: QualityGateState) -> dict[str, Any]:
    """Execute selected tests safely."""
    start = time.perf_counter()
    plan = state.get("validation_plan") or {}
    if plan.get("skip_tests"):
        return {
            "test_results": {
                "executed": 0,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "reason": "skipped_by_plan",
            },
            "phase": "test_execution_skipped",
        }

    tests = list(state.get("tests_to_execute") or plan.get("unit_tests") or [])
    if not tests:
        return {
            "test_results": {
                "executed": 0,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "reason": "no_tests_selected",
            },
            "phase": "test_execution_skipped",
        }

    profile = state.get("repository_profile") or {}
    framework = (profile.get("framework") or {}).get("test_framework") or "pytest"
    runner_name = "pytest"
    fw = (framework or "").lower()
    if "playwright" in fw:
        runner_name = "playwright"
    elif "jest" in fw or "mocha" in fw:
        runner_name = "npm"
    elif framework == "go_test":
        runner_name = "go"
    elif framework == "dotnet":
        runner_name = "dotnet"

    config = state.get("config") or {}
    execution = config.get("execution") or {}
    timeout_min = int(execution.get("timeout_minutes") or 30)
    allowlist = execution.get("allowlist_commands")

    runner = TestRunner(
        state["repository_path"],
        timeout_seconds=timeout_min * 60,
        allowlist=allowlist,
    )

    try:
        result = runner.run(tests, runner=runner_name)
        summary = result.to_summary_dict()
    except PermissionError as e:
        logger.error("Test execution blocked by policy: %s", e)
        summary = {
            "executed": 0,
            "passed": 0,
            "failed": 0,
            "exit_code": 2,
            "error": str(e),
            "reason": "permission_denied",
        }
    except Exception as e:
        logger.exception("Test execution failed")
        summary = {
            "executed": 0,
            "passed": 0,
            "failed": 0,
            "exit_code": 3,
            "error": str(e),
            "reason": "execution_error",
        }

    audit = list(state.get("audit_events") or [])
    audit.append(
        {
            "event": "test_execution",
            "executed": summary.get("executed", 0),
            "passed": summary.get("passed", 0),
            "failed": summary.get("failed", 0),
            "duration_s": round(time.perf_counter() - start, 3),
        }
    )
    timeline = dict(state.get("execution_timeline") or {})
    timeline["test_execution"] = round(time.perf_counter() - start, 3)

    logger.info(
        "Test execution: executed=%s passed=%s failed=%s",
        summary.get("executed"),
        summary.get("passed"),
        summary.get("failed"),
    )

    return {
        "test_results": summary,
        "audit_events": audit,
        "execution_timeline": timeline,
        "phase": "test_execution",
    }
