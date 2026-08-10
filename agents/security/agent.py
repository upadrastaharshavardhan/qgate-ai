"""Security Analysis Agent — deterministic scanners first."""

from __future__ import annotations

import logging
import time
from typing import Any

from core.state.quality_gate_state import QualityGateState
from tools.security.scanner import SecurityScanner

logger = logging.getLogger(__name__)


def security_analysis_node(state: QualityGateState) -> dict[str, Any]:
    start = time.perf_counter()
    config = state.get("config") or {}
    analysis = config.get("analysis") or {}
    if analysis.get("security") is False:
        return {
            "security_findings": [],
            "phase": "security_skipped",
        }

    repo = state["repository_path"]
    files = state.get("changed_files") or []
    # Also scan newly added files
    files = list(dict.fromkeys(files + (state.get("added_files") or [])))

    scanner = SecurityScanner(repo)
    findings = scanner.scan_files(files)

    audit = list(state.get("audit_events") or [])
    audit.append(
        {
            "event": "security_analysis",
            "files_scanned": len(files),
            "findings": len(findings),
            "critical": sum(1 for f in findings if f.severity.value == "critical"),
            "duration_s": round(time.perf_counter() - start, 3),
        }
    )
    timeline = dict(state.get("execution_timeline") or {})
    timeline["security_analysis"] = round(time.perf_counter() - start, 3)

    logger.info("Security analysis: %d findings in %d files", len(findings), len(files))
    return {
        "security_findings": [f.model_dump() for f in findings],
        "audit_events": audit,
        "execution_timeline": timeline,
        "phase": "security_analysis",
    }
