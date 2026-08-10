"""Map changed source files to candidate tests (P0–P3 ranking)."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TestImpactAnalyzer:
    """Heuristic test selection from changed paths and symbols."""

    def __init__(self, repository_path: str | Path) -> None:
        self.root = Path(repository_path).resolve()

    def select(
        self,
        changed_files: list[str],
        all_tests: list[str],
        changed_symbols: list[dict[str, Any]] | None = None,
        source_dirs: list[str] | None = None,
    ) -> dict[str, Any]:
        """Return ranked candidate tests.

        Priority:
          P0 — same module / direct name match
          P1 — same directory / related name
          P2 — same top-level package area
          P3 — unrelated (not selected by default)
        """
        changed_symbols = changed_symbols or []
        source_dirs = source_dirs or ["src/", "lib/", "app/"]

        p0: list[str] = []
        p1: list[str] = []
        p2: list[str] = []

        # Normalize changed stems
        changed_stems: set[str] = set()
        changed_dirs: set[str] = set()
        for f in changed_files:
            p = Path(f)
            stem = p.stem
            if stem.startswith("test_"):
                stem = stem[5:]
            elif stem.endswith("_test"):
                stem = stem[:-5]
            changed_stems.add(stem.lower())
            if p.parent.parts:
                changed_dirs.add(str(p.parent).replace("\\", "/"))

        symbol_names = {s.get("name", "").lower() for s in changed_symbols if s.get("name")}

        for test_path in all_tests:
            tp = Path(test_path)
            tstem = tp.stem.lower()
            if tstem.startswith("test_"):
                tstem = tstem[5:]
            elif tstem.endswith("_test"):
                tstem = tstem[:-5]
            tdir = str(tp.parent).replace("\\", "/")

            # P0: direct stem match or symbol name in path
            if tstem in changed_stems or any(s and s in test_path.lower() for s in symbol_names):
                p0.append(test_path)
                continue
            # Same directory (source ↔ tests mapping)
            mapped = False
            for cd in changed_dirs:
                # e.g. src/payment ↔ tests/payment
                cd_leaf = Path(cd).name.lower()
                if cd_leaf and cd_leaf in tdir.lower():
                    p1.append(test_path)
                    mapped = True
                    break
                if cd.replace("src/", "tests/") in tdir or cd.replace("lib/", "tests/") in tdir:
                    p1.append(test_path)
                    mapped = True
                    break
            if mapped:
                continue
            # P2: shared top-level segment
            for cf in changed_files:
                parts = Path(cf).parts
                if len(parts) >= 2 and parts[0] in ("src", "lib", "app", "tests"):
                    area = parts[1].lower() if len(parts) > 1 else ""
                else:
                    area = parts[0].lower() if parts else ""
                if area and area in test_path.lower() and area not in (".", "tests", "test"):
                    p2.append(test_path)
                    break

        # Dedup across ranks (keep highest priority)
        seen: set[str] = set()
        def dedup(items: list[str]) -> list[str]:
            out = []
            for x in items:
                if x not in seen:
                    seen.add(x)
                    out.append(x)
            return out

        p0 = dedup(p0)
        p1 = dedup(p1)
        p2 = dedup(p2)

        # Default execution set: P0 + P1 (cap for Phase 2)
        to_execute = (p0 + p1)[:50]

        return {
            "p0": p0,
            "p1": p1,
            "p2": p2,
            "p3_count": max(0, len(all_tests) - len(seen)),
            "candidate_tests": p0 + p1 + p2,
            "tests_to_execute": to_execute,
            "impacted_tests": p0 + p1,
            "total_discovered": len(all_tests),
        }
