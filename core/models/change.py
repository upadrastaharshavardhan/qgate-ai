"""Git change and symbol models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class FileChange(BaseModel):
    path: str
    change_type: Literal["added", "modified", "deleted", "renamed"]
    old_path: str | None = None
    additions: int = 0
    deletions: int = 0
    language: str | None = None


class ChangedSymbol(BaseModel):
    """A function, class, method, or other symbol that changed."""

    name: str
    kind: Literal["function", "class", "method", "module", "variable", "other"] = "other"
    file_path: str
    start_line: int | None = None
    end_line: int | None = None
    signature: str | None = None
    change_type: Literal["added", "modified", "deleted"] = "modified"
    callers: list[str] = Field(default_factory=list)
    callees: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChangeSummary(BaseModel):
    """High-level summary of the git change under analysis."""

    base_commit: str
    head_commit: str
    source_branch: str | None = None
    target_branch: str | None = None
    commit_message: str = ""
    author: str | None = None
    changed_files: list[FileChange] = Field(default_factory=list)
    added_files: list[str] = Field(default_factory=list)
    modified_files: list[str] = Field(default_factory=list)
    deleted_files: list[str] = Field(default_factory=list)
    renamed_files: list[dict[str, str]] = Field(default_factory=list)
    changed_symbols: list[ChangedSymbol] = Field(default_factory=list)
    total_additions: int = 0
    total_deletions: int = 0
    diff_stat: str = ""
    raw_diff_summary: str = ""  # truncated for state size
