"""Quality memory store — SQLite by default, Postgres-ready URL."""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, select, desc, func
from sqlalchemy.orm import Session, sessionmaker

from core.memory.models import (
    AnalysisRecord,
    Base,
    FindingRecord,
    HotspotRecord,
    TestFailureRecord,
)

logger = logging.getLogger(__name__)


def _repo_id(repository_path: str) -> str:
    """Stable id for a repo path (not secrets)."""
    resolved = str(Path(repository_path).resolve())
    return hashlib.sha256(resolved.encode()).hexdigest()[:24]


def _finding_fingerprint(category: str, title: str, files: list[str] | None = None) -> str:
    key = f"{category}|{title}|{','.join(sorted(files or []))}"
    return hashlib.sha256(key.encode()).hexdigest()[:32]


class MemoryStore:
    """Persistent quality memory.

    SQLite path example: sqlite:////abs/path/.qgate/memory.db
    Postgres example: postgresql+psycopg://user:pass@host/db
    """

    def __init__(self, database_url: str) -> None:
        connect_args: dict[str, Any] = {}
        if database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        self.engine = create_engine(database_url, future=True, connect_args=connect_args)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False, future=True)

    def session(self) -> Session:
        return self.SessionLocal()

    # ── write paths ──────────────────────────────────────────────

    def record_analysis(
        self,
        *,
        repository_path: str,
        base_commit: str,
        head_commit: str,
        decision: str,
        quality_score: float,
        risk_score: float,
        confidence: float,
        changed_files: list[str],
        tests_executed: int = 0,
        tests_failed: int = 0,
        final_reason: str = "",
        source_branch: str = "",
        target_branch: str = "",
        payload: dict[str, Any] | None = None,
    ) -> int:
        rid = _repo_id(repository_path)
        with self.session() as s:
            rec = AnalysisRecord(
                repository_id=rid,
                base_commit=base_commit,
                head_commit=head_commit,
                source_branch=source_branch,
                target_branch=target_branch,
                decision=decision,
                quality_score=quality_score,
                risk_score=risk_score,
                confidence=confidence,
                changed_files_count=len(changed_files),
                tests_executed=tests_executed,
                tests_failed=tests_failed,
                final_reason=final_reason[:2000],
                changed_files=changed_files[:200],
                payload=payload or {},
            )
            s.add(rec)
            s.commit()
            analysis_id = rec.id

            # Update hotspots
            for f in changed_files[:100]:
                self._bump_hotspot(
                    s,
                    rid,
                    f,
                    blocked=(decision == "BLOCK"),
                    risk=risk_score,
                    commit=head_commit,
                )
            s.commit()
            return analysis_id

    def record_findings(
        self,
        *,
        repository_path: str,
        head_commit: str,
        findings: list[dict[str, Any]],
    ) -> None:
        rid = _repo_id(repository_path)
        with self.session() as s:
            for f in findings:
                files = f.get("impacted_files") or []
                if isinstance(files, dict):
                    files = list(files)
                fp = _finding_fingerprint(
                    str(f.get("category", "")),
                    str(f.get("title", "")),
                    list(files),
                )
                existing = s.scalar(
                    select(FindingRecord).where(
                        FindingRecord.repository_id == rid,
                        FindingRecord.fingerprint == fp,
                    )
                )
                if existing:
                    if existing.status in {"false_positive", "ignored"}:
                        continue  # respect developer suppression
                    existing.times_seen += 1
                    existing.last_seen_commit = head_commit
                    existing.severity = str(f.get("severity", existing.severity))
                else:
                    s.add(
                        FindingRecord(
                            repository_id=rid,
                            finding_key=fp,
                            fingerprint=fp,
                            category=str(f.get("category", "")),
                            severity=str(f.get("severity", "medium")),
                            title=str(f.get("title", ""))[:512],
                            description=str(f.get("description", ""))[:4000],
                            status=str(f.get("status", "new")),
                            confidence=float(f.get("confidence") or 0.8),
                            impacted_files=list(files)[:50],
                            source_agent=str(f.get("source_agent", "")),
                            last_seen_commit=head_commit,
                        )
                    )
            s.commit()

    def record_test_failures(
        self,
        *,
        repository_path: str,
        head_commit: str,
        investigations: list[dict[str, Any]],
    ) -> None:
        rid = _repo_id(repository_path)
        with self.session() as s:
            for inv in investigations:
                nodeid = str(inv.get("test_nodeid", ""))
                classification = str(inv.get("classification", "UNKNOWN"))
                # Flaky heuristic: same test failed with different classifications before
                prior = s.scalars(
                    select(TestFailureRecord)
                    .where(
                        TestFailureRecord.repository_id == rid,
                        TestFailureRecord.test_nodeid == nodeid,
                    )
                    .order_by(desc(TestFailureRecord.created_at))
                    .limit(5)
                ).all()
                is_flaky = False
                if len(prior) >= 2:
                    classes = {p.classification for p in prior}
                    if "FLAKY_TEST" in classes or len(classes) > 1:
                        is_flaky = True
                if classification == "FLAKY_TEST":
                    is_flaky = True

                s.add(
                    TestFailureRecord(
                        repository_id=rid,
                        test_nodeid=nodeid,
                        classification=classification,
                        head_commit=head_commit,
                        related_files=list(inv.get("related_changed_files") or [])[:30],
                        message=str(inv.get("rationale", ""))[:2000],
                        is_flaky_candidate=is_flaky,
                    )
                )

                for fpath in inv.get("related_changed_files") or []:
                    self._bump_hotspot(
                        s, rid, str(fpath), failed=True, commit=head_commit
                    )
            s.commit()

    def mark_finding_status(
        self,
        repository_path: str,
        fingerprint: str,
        status: str,
    ) -> bool:
        rid = _repo_id(repository_path)
        with self.session() as s:
            rec = s.scalar(
                select(FindingRecord).where(
                    FindingRecord.repository_id == rid,
                    FindingRecord.fingerprint == fingerprint,
                )
            )
            if not rec:
                return False
            rec.status = status
            s.commit()
            return True

    def _bump_hotspot(
        self,
        s: Session,
        rid: str,
        file_path: str,
        *,
        blocked: bool = False,
        failed: bool = False,
        risk: float = 0.0,
        commit: str = "",
    ) -> None:
        hs = s.scalar(
            select(HotspotRecord).where(
                HotspotRecord.repository_id == rid,
                HotspotRecord.file_path == file_path,
            )
        )
        if not hs:
            hs = HotspotRecord(
                repository_id=rid,
                file_path=file_path,
                change_count=0,
                failure_count=0,
                block_count=0,
                risk_score_avg=0.0,
            )
            s.add(hs)
        hs.change_count += 1
        if failed:
            hs.failure_count += 1
        if blocked:
            hs.block_count += 1
        if risk:
            # running average
            n = max(1, hs.change_count)
            hs.risk_score_avg = ((hs.risk_score_avg * (n - 1)) + risk) / n
        if commit:
            hs.last_commit = commit

    # ── read paths ───────────────────────────────────────────────

    def get_historical_context(
        self,
        repository_path: str,
        changed_files: list[str] | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        rid = _repo_id(repository_path)
        changed_files = changed_files or []
        with self.session() as s:
            recent = s.scalars(
                select(AnalysisRecord)
                .where(AnalysisRecord.repository_id == rid)
                .order_by(desc(AnalysisRecord.created_at))
                .limit(limit)
            ).all()

            total = len(recent)
            blocks = sum(1 for a in recent if a.decision == "BLOCK")
            failure_rate = (blocks / total) if total else 0.0
            avg_risk = (sum(a.risk_score for a in recent) / total) if total else 0.0

            # Hotspots overlapping current change
            hotspots = []
            if changed_files:
                rows = s.scalars(
                    select(HotspotRecord).where(
                        HotspotRecord.repository_id == rid,
                        HotspotRecord.file_path.in_(changed_files),
                    )
                ).all()
                hotspots = [
                    {
                        "file_path": h.file_path,
                        "change_count": h.change_count,
                        "failure_count": h.failure_count,
                        "block_count": h.block_count,
                        "risk_score_avg": round(h.risk_score_avg, 1),
                    }
                    for h in rows
                ]

            # Known false positives
            fps = s.scalars(
                select(FindingRecord).where(
                    FindingRecord.repository_id == rid,
                    FindingRecord.status.in_(["false_positive", "ignored"]),
                )
            ).all()
            suppressed = [
                {"fingerprint": f.fingerprint, "title": f.title, "status": f.status}
                for f in fps
            ]

            # Flaky tests
            flaky = s.scalars(
                select(TestFailureRecord)
                .where(
                    TestFailureRecord.repository_id == rid,
                    TestFailureRecord.is_flaky_candidate.is_(True),
                )
                .order_by(desc(TestFailureRecord.created_at))
                .limit(20)
            ).all()
            flaky_tests = list({f.test_nodeid for f in flaky})

            # Similar past failures for changed files
            similar_failures = []
            if changed_files:
                rows = s.scalars(
                    select(TestFailureRecord)
                    .where(TestFailureRecord.repository_id == rid)
                    .order_by(desc(TestFailureRecord.created_at))
                    .limit(50)
                ).all()
                for r in rows:
                    related = r.related_files or []
                    if any(f in related for f in changed_files):
                        similar_failures.append(
                            {
                                "test_nodeid": r.test_nodeid,
                                "classification": r.classification,
                                "commit": r.head_commit,
                            }
                        )
                similar_failures = similar_failures[:10]

            return {
                "failure_rate": failure_rate,
                "avg_risk": avg_risk,
                "recent_decisions": [
                    {
                        "decision": a.decision,
                        "risk": a.risk_score,
                        "quality": a.quality_score,
                        "commit": a.head_commit[:8],
                        "files": a.changed_files_count,
                    }
                    for a in recent[:10]
                ],
                "hotspots": hotspots,
                "suppressed_findings": suppressed,
                "flaky_tests": flaky_tests,
                "similar_failures": similar_failures,
                "analysis_count": total,
                "coverage_risk": min(40.0, failure_rate * 100),
            }

    def get_test_relevance(
        self,
        repository_path: str,
        changed_files: list[str],
    ) -> dict[str, float]:
        """Historical probability: changed file → failing test (self-improving selection)."""
        rid = _repo_id(repository_path)
        scores: dict[str, float] = {}
        with self.session() as s:
            rows = s.scalars(
                select(TestFailureRecord)
                .where(TestFailureRecord.repository_id == rid)
                .order_by(desc(TestFailureRecord.created_at))
                .limit(200)
            ).all()
            counts: dict[str, int] = {}
            for r in rows:
                related = r.related_files or []
                if any(f in related for f in changed_files):
                    counts[r.test_nodeid] = counts.get(r.test_nodeid, 0) + 1
            total = sum(counts.values()) or 1
            scores = {k: round(v / total, 3) for k, v in counts.items()}
        return scores


_STORE: MemoryStore | None = None


def get_memory_store(config: dict[str, Any] | None = None) -> MemoryStore | None:
    """Return a MemoryStore if memory is enabled in config; else None."""
    global _STORE
    config = config or {}
    mem = config.get("memory") or {}
    # Also accept nested from QGateConfig.raw
    if not mem and config.get("raw"):
        mem = (config.get("raw") or {}).get("memory") or {}

    enabled = mem.get("enabled", True)  # default on for Phase 4
    if enabled is False:
        return None

    if _STORE is not None:
        return _STORE

    backend = (mem.get("backend") or "sqlite").lower()
    if backend in ("sqlite", "sqlite3"):
        path = mem.get("path") or ".qgate/memory.db"
        p = Path(path)
        if not p.is_absolute():
            # relative to cwd
            p = Path.cwd() / p
        p.parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{p.resolve()}"
    else:
        url = mem.get("url") or mem.get("path") or "sqlite:///.qgate/memory.db"

    try:
        _STORE = MemoryStore(url)
        logger.info("Quality memory enabled: %s", url.split("@")[-1] if "@" in url else url)
        return _STORE
    except Exception as e:
        logger.warning("Memory store unavailable: %s", e)
        return None


def reset_memory_store() -> None:
    global _STORE
    _STORE = None
