"""Report models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from core.models.decision import GateDecision
from core.models.findings import Finding
from core.models.repository import RepositoryProfile
from core.models.change import ChangeSummary


class QualityGateReport(BaseModel):
    """Complete report produced at the end of analysis."""

    report_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    repository_path: str
    decision: GateDecision
    repository_profile: RepositoryProfile | None = None
    change_summary: ChangeSummary | None = None
    all_findings: list[Finding] = Field(default_factory=list)
    audit_events: list[dict[str, Any]] = Field(default_factory=list)
    execution_timeline: dict[str, float] = Field(default_factory=dict)
    version: str = "0.1.0"
    metadata: dict[str, Any] = Field(default_factory=dict)
