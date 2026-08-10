"""GitTool — safe, structured Git operations for Q-GATE AI."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

from core.models.change import ChangeSummary, FileChange

logger = logging.getLogger(__name__)


class GitTool:
    """Wrapper around GitPython with structured outputs and safety."""

    def __init__(self, repository_path: str | Path) -> None:
        self.path = Path(repository_path).resolve()
        if not self.path.exists():
            raise FileNotFoundError(f"Repository path does not exist: {self.path}")
        try:
            self.repo = Repo(self.path)
        except InvalidGitRepositoryError as e:
            raise ValueError(f"Not a git repository: {self.path}") from e

    def resolve_commit(self, ref: str) -> str:
        """Resolve a branch/tag/SHA to a full commit SHA."""
        try:
            return self.repo.commit(ref).hexsha
        except Exception as e:
            raise ValueError(f"Cannot resolve ref '{ref}': {e}") from e

    def get_commit_message(self, ref: str = "HEAD") -> str:
        try:
            return self.repo.commit(ref).message.strip()
        except Exception:
            return ""

    def get_author(self, ref: str = "HEAD") -> str:
        try:
            c = self.repo.commit(ref)
            return f"{c.author.name} <{c.author.email}>"
        except Exception:
            return ""

    def get_changed_files(
        self,
        base: str,
        head: str = "HEAD",
    ) -> tuple[list[str], list[str], list[str], list[dict[str, str]]]:
        """Return (modified, added, deleted, renamed)."""
        base_sha = self.resolve_commit(base)
        head_sha = self.resolve_commit(head)
        diff_index = self.repo.commit(base_sha).diff(head_sha)

        modified: list[str] = []
        added: list[str] = []
        deleted: list[str] = []
        renamed: list[dict[str, str]] = []

        for d in diff_index:
            a_path = d.a_path or ""
            b_path = d.b_path or ""
            if d.change_type == "A":
                added.append(b_path)
            elif d.change_type == "D":
                deleted.append(a_path)
            elif d.change_type == "R":
                renamed.append({"old": a_path, "new": b_path})
                modified.append(b_path)
            else:
                # M, T, etc.
                modified.append(b_path or a_path)

        return modified, added, deleted, renamed

    def get_diff_stat(self, base: str, head: str = "HEAD") -> str:
        try:
            return self.repo.git.diff(base, head, stat=True)
        except GitCommandError as e:
            logger.warning("diff --stat failed: %s", e)
            return ""

    def get_diff_summary(self, base: str, head: str = "HEAD", max_chars: int = 50_000) -> str:
        """Return a truncated unified diff for analysis."""
        try:
            raw = self.repo.git.diff(base, head, unified=3)
            if len(raw) > max_chars:
                return raw[:max_chars] + "\n\n... [diff truncated] ..."
            return raw
        except GitCommandError as e:
            logger.warning("diff failed: %s", e)
            return ""

    def get_name_only(self, base: str, head: str = "HEAD") -> list[str]:
        try:
            out = self.repo.git.diff(base, head, name_only=True)
            return [p for p in out.splitlines() if p.strip()]
        except GitCommandError:
            return []

    def analyze_change(self, base: str, head: str = "HEAD") -> ChangeSummary:
        """Produce a structured ChangeSummary."""
        base_sha = self.resolve_commit(base)
        head_sha = self.resolve_commit(head)
        modified, added, deleted, renamed = self.get_changed_files(base_sha, head_sha)
        all_changed = sorted(set(modified + added + deleted + [r["new"] for r in renamed]))

        # Line counts via numstat
        total_add = 0
        total_del = 0
        file_changes: list[FileChange] = []
        try:
            numstat = self.repo.git.diff(base_sha, head_sha, numstat=True)
            for line in numstat.splitlines():
                parts = line.split("\t")
                if len(parts) < 3:
                    continue
                a, d, path = parts[0], parts[1], parts[2]
                add = int(a) if a.isdigit() else 0
                dele = int(d) if d.isdigit() else 0
                total_add += add
                total_del += dele
                ctype = "modified"
                if path in added:
                    ctype = "added"
                elif path in deleted:
                    ctype = "deleted"
                file_changes.append(
                    FileChange(path=path, change_type=ctype, additions=add, deletions=dele)
                )
        except GitCommandError:
            for p in all_changed:
                ctype = "modified"
                if p in added:
                    ctype = "added"
                elif p in deleted:
                    ctype = "deleted"
                file_changes.append(FileChange(path=p, change_type=ctype))

        return ChangeSummary(
            base_commit=base_sha,
            head_commit=head_sha,
            commit_message=self.get_commit_message(head_sha),
            author=self.get_author(head_sha),
            changed_files=file_changes,
            added_files=added,
            modified_files=modified,
            deleted_files=deleted,
            renamed_files=renamed,
            total_additions=total_add,
            total_deletions=total_del,
            diff_stat=self.get_diff_stat(base_sha, head_sha),
            raw_diff_summary=self.get_diff_summary(base_sha, head_sha),
        )

    def current_branch(self) -> str:
        try:
            return self.repo.active_branch.name
        except Exception:
            return "HEAD"
