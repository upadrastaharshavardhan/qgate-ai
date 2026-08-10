"""ORM / DTO models for quality memory."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class AnalysisRecord(Base):
    """One quality-gate run for a commit."""

    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repository_id: Mapped[str] = mapped_column(String(256), index=True)
    base_commit: Mapped[str] = mapped_column(String(64), default="")
    head_commit: Mapped[str] = mapped_column(String(64), index=True)
    source_branch: Mapped[str] = mapped_column(String(128), default="")
    target_branch: Mapped[str] = mapped_column(String(128), default="")
    decision: Mapped[str] = mapped_column(String(32), index=True)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    changed_files_count: Mapped[int] = mapped_column(Integer, default=0)
    tests_executed: Mapped[int] = mapped_column(Integer, default=0)
    tests_failed: Mapped[int] = mapped_column(Integer, default=0)
    final_reason: Mapped[str] = mapped_column(Text, default="")
    changed_files: Mapped[dict[str, Any]] = mapped_column(JSON, default=list)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class FindingRecord(Base):
    """Persisted finding with lifecycle status."""

    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repository_id: Mapped[str] = mapped_column(String(256), index=True)
    finding_key: Mapped[str] = mapped_column(String(512), index=True)  # stable hash key
    category: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="new", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    impacted_files: Mapped[dict[str, Any]] = mapped_column(JSON, default=list)
    source_agent: Mapped[str] = mapped_column(String(64), default="")
    times_seen: Mapped[int] = mapped_column(Integer, default=1)
    last_seen_commit: Mapped[str] = mapped_column(String(64), default="")
    fingerprint: Mapped[str] = mapped_column(String(128), index=True, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class TestFailureRecord(Base):
    """Historical test failure for correlation and flaky detection."""

    __tablename__ = "test_failures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repository_id: Mapped[str] = mapped_column(String(256), index=True)
    test_nodeid: Mapped[str] = mapped_column(String(512), index=True)
    classification: Mapped[str] = mapped_column(String(64), default="UNKNOWN")
    head_commit: Mapped[str] = mapped_column(String(64), default="")
    related_files: Mapped[dict[str, Any]] = mapped_column(JSON, default=list)
    message: Mapped[str] = mapped_column(Text, default="")
    is_flaky_candidate: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class HotspotRecord(Base):
    """Files/modules with elevated defect density."""

    __tablename__ = "hotspots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repository_id: Mapped[str] = mapped_column(String(256), index=True)
    file_path: Mapped[str] = mapped_column(String(512), index=True)
    change_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    block_count: Mapped[int] = mapped_column(Integer, default=0)
    risk_score_avg: Mapped[float] = mapped_column(Float, default=0.0)
    last_commit: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
