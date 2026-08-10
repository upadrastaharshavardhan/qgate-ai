"""Quality and risk scoring models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class QualityScoreBreakdown(BaseModel):
    overall: float = Field(ge=0.0, le=100.0, default=100.0)
    code_quality: float = Field(ge=0.0, le=100.0, default=100.0)
    test_health: float = Field(ge=0.0, le=100.0, default=100.0)
    security: float = Field(ge=0.0, le=100.0, default=100.0)
    regression_risk: float = Field(ge=0.0, le=100.0, default=100.0)  # inverted: higher = better
    architecture: float = Field(ge=0.0, le=100.0, default=100.0)
    dependency_health: float = Field(ge=0.0, le=100.0, default=100.0)
    ai_confidence: float = Field(ge=0.0, le=100.0, default=100.0)
    weights: dict[str, float] = Field(default_factory=dict)
    explanation: str = ""


class RiskScoreBreakdown(BaseModel):
    overall: float = Field(ge=0.0, le=100.0, default=0.0)
    change_size: float = Field(ge=0.0, le=100.0, default=0.0)
    complexity: float = Field(ge=0.0, le=100.0, default=0.0)
    criticality: float = Field(ge=0.0, le=100.0, default=0.0)
    historical_failure: float = Field(ge=0.0, le=100.0, default=0.0)
    test_coverage: float = Field(ge=0.0, le=100.0, default=0.0)  # higher = more risk if low coverage
    dependency_impact: float = Field(ge=0.0, le=100.0, default=0.0)
    security_impact: float = Field(ge=0.0, le=100.0, default=0.0)
    level: str = "LOW"  # LOW | MEDIUM | HIGH | VERY_HIGH | CRITICAL
    explanation: str = ""
