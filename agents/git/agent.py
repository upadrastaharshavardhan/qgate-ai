"""Git Change Intelligence Agent."""

from __future__ import annotations

import logging
import time
from typing import Any

from core.state.quality_gate_state import QualityGateState
from tools.git.git_tool import GitTool

logger = logging.getLogger(__name__)


def git_change_analysis_node(state: QualityGateState) -> dict[str, Any]:
    """Analyze git diff between base and head."""
    start = time.perf_counter()
    repo_path = state["repository_path"]
    base = state.get("base_commit") or "main"
    head = state.get("head_commit") or "HEAD"

    logger.info("Git change analysis: %s..%s", base, head)
    tool = GitTool(repo_path)
    summary = tool.analyze_change(base, head)

    # Also set branch names if missing
    source = state.get("source_branch") or tool.current_branch()
    target = state.get("target_branch") or "main"

    audit = list(state.get("audit_events") or [])
    audit.append(
        {
            "event": "git_change_analysis",
            "base": summary.base_commit[:8],
            "head": summary.head_commit[:8],
            "files_changed": len(summary.changed_files),
            "additions": summary.total_additions,
            "deletions": summary.total_deletions,
            "duration_s": round(time.perf_counter() - start, 3),
        }
    )

    timeline = dict(state.get("execution_timeline") or {})
    timeline["git_change_analysis"] = round(time.perf_counter() - start, 3)

    return {
        "change_summary": summary.model_dump(),
        "base_commit": summary.base_commit,
        "head_commit": summary.head_commit,
        "commit_message": summary.commit_message,
        "author": summary.author or "",
        "source_branch": source,
        "target_branch": target,
        "changed_files": [f.path for f in summary.changed_files],
        "added_files": summary.added_files,
        "modified_files": summary.modified_files,
        "deleted_files": summary.deleted_files,
        "renamed_files": summary.renamed_files,
        "git_diff_summary": summary.raw_diff_summary[:20000],
        "audit_events": audit,
        "execution_timeline": timeline,
        "phase": "git_change_analysis",
    }
