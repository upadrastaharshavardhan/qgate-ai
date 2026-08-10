"""Strongly typed shared state for the Q-GATE LangGraph workflow."""

from __future__ import annotations

from typing import Any, TypedDict

from core.models.change import ChangeSummary, ChangedSymbol
from core.models.decision import GateDecision, ValidationPlan
from core.models.findings import Finding
from core.models.repository import RepositoryProfile
from core.models.scoring import QualityScoreBreakdown, RiskScoreBreakdown


class QualityGateState(TypedDict, total=False):
    """Shared state passed through the LangGraph workflow.

    Prefer structured models and references over large raw text.
    """

    # Input context
    repository_path: str
    source_branch: str
    target_branch: str
    base_commit: str
    head_commit: str
    commit_message: str
    author: str
    config: dict[str, Any]

    # Repository intelligence
    repository_profile: dict[str, Any]  # serialized RepositoryProfile
    repository_map: dict[str, Any]
    architecture_map: dict[str, Any]
    dependency_graph: dict[str, Any]

    # Change analysis
    change_summary: dict[str, Any]  # serialized ChangeSummary
    changed_files: list[str]
    added_files: list[str]
    modified_files: list[str]
    deleted_files: list[str]
    renamed_files: list[dict[str, str]]
    git_diff_summary: str  # truncated
    changed_symbols: list[dict[str, Any]]
    impacted_symbols: list[dict[str, Any]]
    impacted_files: list[str]

    # Test impact
    impacted_tests: list[str]
    candidate_tests: list[str]
    tests_to_execute: list[str]
    test_results: dict[str, Any]

    # Findings from agents
    quality_findings: list[dict[str, Any]]
    security_findings: list[dict[str, Any]]
    architecture_findings: list[dict[str, Any]]
    dependency_findings: list[dict[str, Any]]
    regression_findings: list[dict[str, Any]]
    ai_review_findings: list[dict[str, Any]]
    historical_findings: list[dict[str, Any]]

    # Historical context
    historical_context: dict[str, Any]

    # Scoring
    risk_score: float
    quality_score: float
    confidence_score: float
    quality_breakdown: dict[str, Any]
    risk_breakdown: dict[str, Any]

    # Validation & decision
    validation_plan: dict[str, Any]
    blocking_findings: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    recommendations: list[str]
    final_decision: str
    final_reason: str
    gate_decision: dict[str, Any]

    # Observability
    audit_events: list[dict[str, Any]]
    execution_timeline: dict[str, float]
    errors: list[str]
    phase: str


def create_initial_state(
    repository_path: str,
    base_commit: str = "main",
    head_commit: str = "HEAD",
    source_branch: str | None = None,
    target_branch: str | None = None,
    config: dict[str, Any] | None = None,
) -> QualityGateState:
    """Create a clean initial state for a quality gate run."""
    return QualityGateState(
        repository_path=repository_path,
        base_commit=base_commit,
        head_commit=head_commit,
        source_branch=source_branch or "",
        target_branch=target_branch or "main",
        commit_message="",
        author="",
        config=config or {},
        changed_files=[],
        added_files=[],
        modified_files=[],
        deleted_files=[],
        renamed_files=[],
        git_diff_summary="",
        changed_symbols=[],
        impacted_symbols=[],
        impacted_files=[],
        impacted_tests=[],
        candidate_tests=[],
        tests_to_execute=[],
        test_results={},
        quality_findings=[],
        security_findings=[],
        architecture_findings=[],
        dependency_findings=[],
        regression_findings=[],
        ai_review_findings=[],
        historical_findings=[],
        historical_context={},
        risk_score=0.0,
        quality_score=100.0,
        confidence_score=0.0,
        quality_breakdown={},
        risk_breakdown={},
        validation_plan={},
        blocking_findings=[],
        warnings=[],
        recommendations=[],
        final_decision="",
        final_reason="",
        gate_decision={},
        audit_events=[],
        execution_timeline={},
        errors=[],
        phase="init",
    )
