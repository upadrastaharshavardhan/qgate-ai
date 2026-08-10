"""Lightweight symbol extraction from changed files (Python-focused MVP)."""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path
from typing import Any

from core.models.change import ChangedSymbol

logger = logging.getLogger(__name__)


class SymbolAnalyzer:
    """Extract functions/classes from source files without full project indexing."""

    def __init__(self, repository_path: str | Path) -> None:
        self.root = Path(repository_path).resolve()

    def analyze_files(self, file_paths: list[str]) -> list[ChangedSymbol]:
        symbols: list[ChangedSymbol] = []
        for rel in file_paths:
            path = self.root / rel
            if not path.is_file():
                continue
            if path.suffix == ".py":
                symbols.extend(self._python_symbols(rel, path))
            elif path.suffix in {".js", ".ts", ".tsx", ".jsx"}:
                symbols.extend(self._js_like_symbols(rel, path))
            elif path.suffix in {".java", ".go", ".cs"}:
                symbols.extend(self._generic_symbols(rel, path))
        return symbols

    def _python_symbols(self, rel: str, path: Path) -> list[ChangedSymbol]:
        try:
            src = path.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(src)
        except Exception as e:
            logger.debug("AST parse failed for %s: %s", rel, e)
            return self._generic_symbols(rel, path)

        out: list[ChangedSymbol] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                out.append(
                    ChangedSymbol(
                        name=node.name,
                        kind="function",
                        file_path=rel,
                        start_line=getattr(node, "lineno", None),
                        end_line=getattr(node, "end_lineno", None),
                        signature=f"def {node.name}(...)",
                    )
                )
            elif isinstance(node, ast.ClassDef):
                out.append(
                    ChangedSymbol(
                        name=node.name,
                        kind="class",
                        file_path=rel,
                        start_line=getattr(node, "lineno", None),
                        end_line=getattr(node, "end_lineno", None),
                        signature=f"class {node.name}",
                    )
                )
        return out

    def _js_like_symbols(self, rel: str, path: Path) -> list[ChangedSymbol]:
        try:
            src = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return []
        out: list[ChangedSymbol] = []
        for m in re.finditer(
            r"(?:export\s+)?(?:async\s+)?function\s+(\w+)|(?:export\s+)?class\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(",
            src,
        ):
            name = m.group(1) or m.group(2) or m.group(3)
            kind = "class" if m.group(2) else "function"
            line = src[: m.start()].count("\n") + 1
            out.append(
                ChangedSymbol(
                    name=name,
                    kind=kind,  # type: ignore[arg-type]
                    file_path=rel,
                    start_line=line,
                )
            )
        return out

    def _generic_symbols(self, rel: str, path: Path) -> list[ChangedSymbol]:
        try:
            src = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return []
        out: list[ChangedSymbol] = []
        # function / method / class-ish
        for m in re.finditer(
            r"(?:def|func|function|public|private|protected|static)?\s*(?:class|interface)?\s*(\w+)\s*[\(:]",
            src,
        ):
            name = m.group(1)
            if name in {"if", "for", "while", "switch", "return", "import", "from"}:
                continue
            line = src[: m.start()].count("\n") + 1
            kind = "class" if "class" in m.group(0) else "function"
            out.append(
                ChangedSymbol(
                    name=name,
                    kind=kind,  # type: ignore[arg-type]
                    file_path=rel,
                    start_line=line,
                )
            )
        return out[:100]
