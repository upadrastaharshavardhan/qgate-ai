"""Regression Risk Agent — flags high-impact change patterns."""

from __future__ import annotations

import logging
import time
from typing import Any

from core.models.findings import Finding, FindingCategory, FindingSeverity
from core.state.quality_gate_state import QualityGateState

logger = logging.getLogger(__name__)

CRITICAL_PATH_KEYWORDS = (
    "payment",
    "auth",
    "login",
    "password",
    "checkout",
    "billing",
    "security",
    "permission",
    "admin",
    "token",
    "crypto",
)


def regression_risk_node(state: QualityGateState) -> dict[str, Any]:
    start = time.perf_counter()
    findings: list[Finding] = []
    changed = state.get("changed_files") or []
    symbols = state.get("changed_symbols") or []

    critical_files = [f for f in changed if any(k in f.lower() for k in CRITICAL_PATH_KEYWORDS)]
    if critical_files:
        findings.append(
            Finding(
                category=FindingCategory.REGRESSION,
                severity=FindingSeverity.HIGH,
                title="Critical path files modified",
                description="Changes touch security/payment/auth related paths: "
                + ", ".join(critical_files[:8]),
                evidence=critical_files[:8],
                confidence=0.9,
                impacted_files=critical_files,
                recommendation="Ensure targeted tests cover these paths before merge.",
                source_agent="regression_risk",
            )
        )

    # Large symbol churn
    if len(symbols) >= 15:
        findings.append(
            Finding(
                category=FindingCategory.REGRESSION,
                severity=FindingSeverity.MEDIUM,
                title="High symbol churn",
                description=f"{len(symbols)} symbols changed in this commit.",
                evidence=[f"{s.get('name')}@{s.get('file_path')}" for s in symbols[:10]],
                confidence=0.8,
                recommendation="Prefer smaller, focused changes for safer reviews.",
                source_agent="regression_risk",
            )
        )

    # Tests changed without source — lower risk; source without tests — warning handled elsewhere
    test_files = [f for f in changed if "test" in f.lower()]
    source_files = [f for f in changed if f not in test_files and not f.endswith((".md", ".txt", ".yml", ".yaml"))]
    if source_files and not test_files and len(source_files) >= 2:
        findings.append(
            Finding(
                category=FindingCategory.TEST,
                severity=FindingSeverity.MEDIUM,
                title="Source changed without accompanying tests",
                description=f"{len(source_files)} source file(s) changed; no test files in the diff.",
                evidence=source_files[:10],
                confidence=0.75,
                impacted_files=source_files,
                recommendation="Add or update tests for the changed behavior.",
                source_agent="regression_risk",
            )
        )

    audit = list(state.get("audit_events") or [])
    audit.append(
        {
            "event": "regression_risk",
            "findings": len(findings),
            "critical_files": len(critical_files),
            "duration_s": round(time.perf_counter() - start, 3),
        }
    )
    timeline = dict(state.get("execution_timeline") or {})
    timeline["regression_risk"] = round(time.perf_counter() - start, 3)

    return {
        "regression_findings": [f.model_dump() for f in findings],
        "audit_events": audit,
        "execution_timeline": timeline,
        "phase": "regression_risk",
    }
