"""Repository Intelligence Agent — node for LangGraph."""

from __future__ import annotations

import logging
import time
from typing import Any

from core.state.quality_gate_state import QualityGateState
from tools.repository.scanner import RepositoryScanner

logger = logging.getLogger(__name__)


def repository_discovery_node(state: QualityGateState) -> dict[str, Any]:
    """Discover repository language, structure, and tooling."""
    start = time.perf_counter()
    repo_path = state["repository_path"]
    config = state.get("config") or {}
    ignore = config.get("ignore_patterns") or []

    logger.info("Repository discovery starting for %s", repo_path)
    scanner = RepositoryScanner(repo_path, ignore_patterns=ignore)
    profile = scanner.scan()

    audit = list(state.get("audit_events") or [])
    audit.append(
        {
            "event": "repository_discovery",
            "language": profile.language.primary,
            "test_framework": profile.framework.test_framework,
            "duration_s": round(time.perf_counter() - start, 3),
        }
    )

    timeline = dict(state.get("execution_timeline") or {})
    timeline["repository_discovery"] = round(time.perf_counter() - start, 3)

    return {
        "repository_profile": profile.model_dump(),
        "audit_events": audit,
        "execution_timeline": timeline,
        "phase": "repository_discovery",
    }
