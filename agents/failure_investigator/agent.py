"""Failure Investigator Agent.

When targeted tests fail, classify the failure before the policy engine blocks.
Does NOT auto-pass on failure — only explains and scores confidence.
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Any

from core.models.findings import Finding, FindingCategory, FindingSeverity
from core.models.testing import FailureClass, FailureInvestigation
from core.state.quality_gate_state import QualityGateState

logger = logging.getLogger(__name__)

ENV_MARKERS = (
    "connection refused",
    "could not connect",
    "timeout",
    "timed out",
    "network is unreachable",
    "no such host",
    "temporary failure",
    "503",
    "502",
    "econnrefused",
)

FLAKY_MARKERS = (
    "flaky",
    "intermittent",
    "race condition",
    "sometimes",
)

DEP_MARKERS = (
    "modulenotfounderror",
    "importerror",
    "no module named",
    "cannot import",
    "package not found",
)


def failure_investigator_node(state: QualityGateState) -> dict[str, Any]:
    start = time.perf_counter()
    results = state.get("test_results") or {}
    failed_count = int(results.get("failed") or 0) + int(results.get("errors") or 0)

    if failed_count <= 0:
        return {
            "phase": "failure_investigator_skipped",
            "regression_findings": list(state.get("regression_findings") or []),
        }

    failed_tests = results.get("failed_tests") or []
    changed_files = state.get("changed_files") or []
    symbols = state.get("changed_symbols") or []
    symbol_names = [s.get("name", "") for s in symbols if s.get("name")]
    diff = (state.get("git_diff_summary") or "").lower()

    investigations: list[FailureInvestigation] = []
    findings: list[Finding] = []

    for ft in failed_tests:
        nodeid = ft.get("nodeid") or "unknown"
        message = (ft.get("message") or "") + "\n" + (ft.get("traceback") or "")
        msg_l = message.lower()

        classification, confidence, rationale = _classify(
            nodeid=nodeid,
            message=msg_l,
            changed_files=changed_files,
            symbol_names=symbol_names,
            diff=diff,
        )

        related_files = [
            f for f in changed_files if _path_related(nodeid, f)
        ]
        related_syms = [
            s for s in symbol_names if s and s.lower() in msg_l
        ]

        inv = FailureInvestigation(
            test_nodeid=nodeid,
            classification=classification,
            confidence=confidence,
            rationale=rationale,
            related_changed_files=related_files,
            related_symbols=related_syms,
            evidence=[
                f"test={nodeid}",
                f"message={message[:300]}",
                f"changed_files={len(changed_files)}",
            ],
            recommendation=_recommendation(classification),
        )
        investigations.append(inv)

        severity = (
            FindingSeverity.CRITICAL
            if classification == FailureClass.REAL_REGRESSION
            else FindingSeverity.HIGH
            if classification
            in {FailureClass.DEPENDENCY_FAILURE, FailureClass.UNKNOWN}
            else FindingSeverity.MEDIUM
        )

        findings.append(
            Finding(
                category=FindingCategory.REGRESSION
                if classification == FailureClass.REAL_REGRESSION
                else FindingCategory.TEST,
                severity=severity,
                title=f"{classification.value}: {nodeid}",
                description=rationale,
                evidence=inv.evidence,
                confidence=confidence,
                impacted_files=related_files,
                impacted_symbols=related_syms,
                recommendation=inv.recommendation,
                source_agent="failure_investigator",
                metadata={
                    "classification": classification.value,
                    "nodeid": nodeid,
                },
            )
        )

    # Aggregate finding when pytest summary had failures but no parsed tests
    if not failed_tests and failed_count > 0:
        findings.append(
            Finding(
                category=FindingCategory.TEST,
                severity=FindingSeverity.CRITICAL,
                title=f"{failed_count} test(s) failed (details unavailable)",
                description="Targeted test run reported failures but individual results were not parsed.",
                evidence=[f"failed={failed_count}", f"exit_code={results.get('exit_code')}"],
                confidence=0.9,
                recommendation="Re-run tests locally with verbose output and inspect failures.",
                source_agent="failure_investigator",
            )
        )

    audit = list(state.get("audit_events") or [])
    audit.append(
        {
            "event": "failure_investigator",
            "investigations": len(investigations),
            "real_regressions": sum(
                1 for i in investigations if i.classification == FailureClass.REAL_REGRESSION
            ),
            "duration_s": round(time.perf_counter() - start, 3),
        }
    )
    timeline = dict(state.get("execution_timeline") or {})
    timeline["failure_investigator"] = round(time.perf_counter() - start, 3)

    # Merge with existing regression findings
    existing_reg = list(state.get("regression_findings") or [])
    existing_reg.extend(f.model_dump() for f in findings)

    return {
        "regression_findings": existing_reg,
        "historical_context": {
            **(state.get("historical_context") or {}),
            "failure_investigations": [i.model_dump(mode="json") for i in investigations],
        },
        "audit_events": audit,
        "execution_timeline": timeline,
        "phase": "failure_investigator",
    }


def _classify(
    *,
    nodeid: str,
    message: str,
    changed_files: list[str],
    symbol_names: list[str],
    diff: str,
) -> tuple[FailureClass, float, str]:
    if any(m in message for m in DEP_MARKERS):
        return (
            FailureClass.DEPENDENCY_FAILURE,
            0.88,
            "Failure indicates missing or broken dependency/import.",
        )
    if any(m in message for m in ENV_MARKERS):
        return (
            FailureClass.ENVIRONMENT_FAILURE,
            0.8,
            "Failure looks environment/network related rather than pure logic regression.",
        )
    if any(m in message for m in FLAKY_MARKERS):
        return (
            FailureClass.FLAKY_TEST,
            0.7,
            "Message suggests flakiness; consider quarantine and deterministic waits.",
        )

    # Overlap between failing test path and changed files
    related = [f for f in changed_files if _path_related(nodeid, f)]
    symbol_hit = any(s and s.lower() in message for s in symbol_names)

    # Assertion in test that we also changed the test file → possible test defect
    test_file = nodeid.split("::")[0]
    test_file_changed = any(
        test_file.endswith(Path(f).name) or f.endswith(test_file) or test_file in f
        for f in changed_files
    )
    source_changed = any(
        not _is_test_path(f) for f in changed_files
    )

    if related and source_changed and not test_file_changed:
        return (
            FailureClass.REAL_REGRESSION,
            0.9 if symbol_hit else 0.82,
            f"Failing test overlaps changed production code ({', '.join(related[:3])}).",
        )
    if test_file_changed and not source_changed:
        return (
            FailureClass.TEST_DEFECT,
            0.75,
            "Only test files changed; failure may be an incorrect assertion/update.",
        )
    if source_changed and failed_looks_like_assert(message):
        return (
            FailureClass.REAL_REGRESSION,
            0.7,
            "Source changed and assertion failed; likely behavioral regression.",
        )
    if not changed_files:
        return (
            FailureClass.UNKNOWN,
            0.5,
            "No changed files in context; cannot correlate failure.",
        )
    return (
        FailureClass.UNKNOWN,
        0.55,
        "Could not confidently correlate failure to the change set.",
    )


def failed_looks_like_assert(message: str) -> bool:
    return "assert" in message or "assertionerror" in message or "expected" in message


def _is_test_path(path: str) -> bool:
    p = path.lower()
    return "test" in p or p.endswith("_test.py") or "/tests/" in p


def _path_related(nodeid: str, file_path: str) -> bool:
    node = nodeid.lower()
    fp = file_path.lower()
    stem = Path(file_path).stem.lower()
    if stem.startswith("test_"):
        stem = stem[5:]
    if stem and stem in node:
        return True
    parts = Path(file_path).parts
    for part in parts:
        if part.lower() in ("src", "lib", "app", "tests", "test") or len(part) < 3:
            continue
        if part.lower() in node:
            return True
    return False


def _recommendation(c: FailureClass) -> str:
    return {
        FailureClass.REAL_REGRESSION: "Fix the production code or add compensating tests; do not merge until green.",
        FailureClass.TEST_DEFECT: "Update the test expectations if the behavior change is intentional.",
        FailureClass.ENVIRONMENT_FAILURE: "Check CI/environment services, credentials, and network access.",
        FailureClass.FLAKY_TEST: "Stabilize the test (deterministic waits, isolation) before relying on it as a gate.",
        FailureClass.DEPENDENCY_FAILURE: "Install/align dependencies; verify lockfiles.",
        FailureClass.UNKNOWN: "Inspect the failure locally with verbose logs and bisect if needed.",
    }[c]
