"""Gate decision and validation plan models."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from core.models.findings import Finding
from core.models.scoring import QualityScoreBreakdown, RiskScoreBreakdown


class DecisionType(str, Enum):
    PASS = "PASS"
    PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
    BLOCK = "BLOCK"


class ValidationPlan(BaseModel):
    """Plan produced by Validation Planner Agent."""

    static_analysis: bool = True
    security_scan: bool = True
    unit_tests: list[str] = Field(default_factory=list)
    integration_tests: list[str] = Field(default_factory=list)
    e2e_tests: list[str] = Field(default_factory=list)
    full_regression: bool = False
    skip_tests: bool = False
    reason: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class GateDecision(BaseModel):
    """Final quality gate decision."""

    decision: DecisionType
    quality_score: float = 0.0
    risk_score: float = 0.0
    confidence: float = 0.0
    quality_breakdown: QualityScoreBreakdown | None = None
    risk_breakdown: RiskScoreBreakdown | None = None
    blocking_findings: list[Finding] = Field(default_factory=list)
    warnings: list[Finding] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    final_reason: str = ""
    validation_plan: ValidationPlan | None = None
    tests_required: int = 0
    tests_executed: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    changed_files_count: int = 0
    impacted_files_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
