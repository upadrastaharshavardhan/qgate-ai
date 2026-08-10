"""Finding models for quality, security, architecture, etc."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class FindingSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FindingCategory(str, Enum):
    SECURITY = "security"
    CODE_QUALITY = "code_quality"
    ARCHITECTURE = "architecture"
    DEPENDENCY = "dependency"
    REGRESSION = "regression"
    TEST = "test"
    AI_REVIEW = "ai_review"
    HISTORICAL = "historical"
    CONFIGURATION = "configuration"


class FindingStatus(str, Enum):
    NEW = "new"
    CONFIRMED = "confirmed"
    FALSE_POSITIVE = "false_positive"
    RESOLVED = "resolved"
    IGNORED = "ignored"


class Finding(BaseModel):
    """Structured finding produced by any agent."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    category: FindingCategory
    severity: FindingSeverity
    title: str
    description: str
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    impacted_files: list[str] = Field(default_factory=list)
    impacted_symbols: list[str] = Field(default_factory=list)
    recommendation: str = ""
    status: FindingStatus = FindingStatus.NEW
    source_agent: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def is_blocking(self, block_severities: set[FindingSeverity] | None = None) -> bool:
        if block_severities is None:
            block_severities = {FindingSeverity.CRITICAL, FindingSeverity.HIGH}
        return self.severity in block_severities and self.status not in {
            FindingStatus.FALSE_POSITIVE,
            FindingStatus.IGNORED,
            FindingStatus.RESOLVED,
        }
