"""Configuration loading for Q-GATE AI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class QualityGateRules(BaseModel):
    minimum_quality_score: float = 80.0
    maximum_risk_score: float = 60.0
    minimum_ai_confidence: float = 0.75
    block_on: list[str] = Field(
        default_factory=lambda: [
            "critical_security",
            "secret_detected",
            "build_failure",
            "targeted_test_failure",
            "critical_regression",
            "compilation_failure",
        ]
    )
    warnings: list[str] = Field(
        default_factory=lambda: ["medium_security", "missing_tests", "high_complexity"]
    )
    require_full_regression_when: dict[str, Any] = Field(
        default_factory=lambda: {
            "risk_score": 75,
            "changed_files": 25,
            "critical_area_changed": True,
        }
    )


class ScoringWeights(BaseModel):
    code_quality: float = 0.20
    test_health: float = 0.20
    security: float = 0.20
    regression_risk: float = 0.20
    architecture: float = 0.10
    dependency_health: float = 0.05
    ai_confidence: float = 0.05


class RiskWeights(BaseModel):
    change_size: float = 0.15
    complexity: float = 0.15
    criticality: float = 0.20
    historical_failure: float = 0.15
    test_coverage: float = 0.10
    dependency_impact: float = 0.10
    security_impact: float = 0.15


class AnalysisFlags(BaseModel):
    security: bool = True
    architecture: bool = True
    dependencies: bool = True
    historical_analysis: bool = True
    test_impact_analysis: bool = True
    ai_code_review: bool = True
    semantic_impact: bool = True


class ExecutionConfig(BaseModel):
    max_parallel_tests: int = 8
    timeout_minutes: int = 30
    sandbox: bool = True
    allowlist_commands: list[str] = Field(
        default_factory=lambda: ["pytest", "python", "npm", "npx", "mvn", "gradle", "go", "dotnet"]
    )


class LLMConfig(BaseModel):
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    temperature: float = 0.1
    max_tokens: int = 4096
    timeout_seconds: int = 60


class QGateConfig(BaseModel):
    project_name: str = "my-project"
    quality_gate: QualityGateRules = Field(default_factory=QualityGateRules)
    scoring_weights: ScoringWeights = Field(default_factory=ScoringWeights)
    risk_weights: RiskWeights = Field(default_factory=RiskWeights)
    analysis: AnalysisFlags = Field(default_factory=AnalysisFlags)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    ignore_patterns: list[str] = Field(default_factory=list)
    reporting_formats: list[str] = Field(default_factory=lambda: ["json", "html", "markdown"])
    output_dir: str = ".qgate/reports"
    raw: dict[str, Any] = Field(default_factory=dict)


def load_config(path: str | Path | None = None) -> QGateConfig:
    """Load qgate.yaml from the given path or search upward from cwd."""
    if path is None:
        candidates = [
            Path.cwd() / "qgate.yaml",
            Path.cwd() / ".qgate" / "qgate.yaml",
            Path(__file__).resolve().parents[2] / "qgate.yaml",
        ]
        for c in candidates:
            if c.exists():
                path = c
                break
        else:
            return QGateConfig()

    path = Path(path)
    if not path.exists():
        return QGateConfig()

    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    qg = data.get("quality_gate", {})
    scoring = data.get("scoring", {})
    weights = scoring.get("weights", {})
    risk_w = scoring.get("risk_weights", {})
    analysis = data.get("analysis", {})
    execution = data.get("execution", {})
    llm = data.get("llm", {})
    repo = data.get("repository", {})
    reporting = data.get("reporting", {})

    return QGateConfig(
        project_name=data.get("project", {}).get("name", "my-project"),
        quality_gate=QualityGateRules(**qg) if qg else QualityGateRules(),
        scoring_weights=ScoringWeights(**weights) if weights else ScoringWeights(),
        risk_weights=RiskWeights(**risk_w) if risk_w else RiskWeights(),
        analysis=AnalysisFlags(**analysis) if analysis else AnalysisFlags(),
        execution=ExecutionConfig(**execution) if execution else ExecutionConfig(),
        llm=LLMConfig(**llm) if llm else LLMConfig(),
        ignore_patterns=repo.get("ignore_patterns", []),
        reporting_formats=reporting.get("formats", ["json", "html", "markdown"]),
        output_dir=reporting.get("output_dir", ".qgate/reports"),
        raw=data,
    )
