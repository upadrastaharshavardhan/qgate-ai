"""Discover tests in a repository."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class TestDiscoveryTool:
    """Find test files based on conventions."""

    def __init__(self, repository_path: str | Path) -> None:
        self.root = Path(repository_path).resolve()

    def discover(self, language: str = "python", test_dirs: list[str] | None = None) -> list[str]:
        tests: list[str] = []
        test_dirs = test_dirs or []

        patterns: list[str] = []
        if language == "python":
            patterns = ["**/test_*.py", "**/*_test.py", "**/tests/**/*.py"]
        elif language in ("javascript", "typescript"):
            patterns = ["**/*.test.js", "**/*.test.ts", "**/*.spec.js", "**/*.spec.ts", "**/__tests__/**", "**/e2e/**/*.ts", "**/e2e/**/*.js", "**/tests/**/*.spec.ts"]
        elif language == "java":
            patterns = ["**/src/test/**/*.java", "**/*Test.java", "**/*Tests.java"]
        elif language == "go":
            patterns = ["**/*_test.go"]
        else:
            patterns = ["**/test_*", "**/*_test.*", "**/tests/**"]

        ignore = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}

        for pattern in patterns:
            for p in self.root.glob(pattern):
                if not p.is_file():
                    continue
                if any(part in ignore for part in p.parts):
                    continue
                rel = str(p.relative_to(self.root))
                # Prefer files under known test dirs when provided
                tests.append(rel)

        # Deduplicate preserving order
        seen: set[str] = set()
        ordered: list[str] = []
        for t in tests:
            if t not in seen:
                seen.add(t)
                ordered.append(t)
        return ordered
