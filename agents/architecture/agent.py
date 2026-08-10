"""Semantic Code Impact Agent — extract changed symbols and estimate impact radius."""

from __future__ import annotations

import logging
import time
from typing import Any

from core.state.quality_gate_state import QualityGateState
from tools.repository.symbol_analyzer import SymbolAnalyzer

logger = logging.getLogger(__name__)


def semantic_impact_node(state: QualityGateState) -> dict[str, Any]:
    start = time.perf_counter()
    config = state.get("config") or {}
    analysis = config.get("analysis") or {}
    if analysis.get("semantic_impact") is False:
        return {"changed_symbols": [], "impacted_symbols": [], "impacted_files": []}

    files = [
        f
        for f in (state.get("changed_files") or [])
        if not f.endswith((".md", ".txt", ".yml", ".yaml", ".json", ".lock"))
    ]
    analyzer = SymbolAnalyzer(state["repository_path"])
    symbols = analyzer.analyze_files(files)

    # Impacted files heuristic: same directory peers (lightweight)
    impacted_files: set[str] = set(state.get("changed_files") or [])
    from pathlib import Path

    for f in list(impacted_files):
        parent = Path(f).parent
        # Note: we don't walk whole tree for Phase 2; radius = changed + symbol count
        pass

    impacted_symbols = [
        {
            "name": s.name,
            "kind": s.kind,
            "file_path": s.file_path,
            "reason": "changed",
        }
        for s in symbols
    ]

    audit = list(state.get("audit_events") or [])
    audit.append(
        {
            "event": "semantic_impact",
            "symbols": len(symbols),
            "files_analyzed": len(files),
            "duration_s": round(time.perf_counter() - start, 3),
        }
    )
    timeline = dict(state.get("execution_timeline") or {})
    timeline["semantic_impact"] = round(time.perf_counter() - start, 3)

    return {
        "changed_symbols": [s.model_dump() for s in symbols],
        "impacted_symbols": impacted_symbols,
        "impacted_files": sorted(impacted_files),
        "audit_events": audit,
        "execution_timeline": timeline,
        "phase": "semantic_impact",
    }
