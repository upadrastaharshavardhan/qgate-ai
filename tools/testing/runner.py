"""Safe targeted test execution.

The LLM never invokes this directly with arbitrary commands.
Only allowlisted runners are used, with explicit argument construction.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from core.models.testing import IndividualTestResult, TestRunResult, TestStatus

logger = logging.getLogger(__name__)

# Base allowlist — only these executables may be invoked
ALLOWED_RUNNERS = {
    "pytest": ["pytest"],
    "python": ["python", "-m", "pytest"],
    "npm": ["npm", "test"],
    "npx": ["npx"],
    "playwright": ["npx", "playwright", "test"],
    "mvn": ["mvn", "test"],
    "gradle": ["gradle", "test"],
    "go": ["go", "test"],
    "dotnet": ["dotnet", "test"],
}


class TestRunner:
    """Execute selected tests with timeouts and structured capture."""

    def __init__(
        self,
        repository_path: str | Path,
        *,
        timeout_seconds: int = 600,
        allowlist: list[str] | None = None,
    ) -> None:
        self.root = Path(repository_path).resolve()
        self.timeout_seconds = timeout_seconds
        self.allowlist = set(allowlist or list(ALLOWED_RUNNERS.keys()))

    def run(
        self,
        test_paths: list[str],
        *,
        runner: str = "pytest",
        extra_args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> TestRunResult:
        if not test_paths:
            return TestRunResult(
                command=[],
                exit_code=0,
                passed=0,
                failed=0,
                executed=0,
                runner=runner,
                metadata={"reason": "no_tests_selected"},
            )

        if runner not in self.allowlist and runner not in ALLOWED_RUNNERS:
            raise PermissionError(f"Runner '{runner}' is not allowlisted")

        if runner in ("pytest", "python"):
            return self._run_pytest(test_paths, extra_args=extra_args, env=env)
        if runner == "npm":
            return self._run_simple(["npm", "test", "--", *test_paths], runner="npm", env=env)
        if runner in ("playwright", "npx"):
            return self._run_playwright(test_paths, extra_args=extra_args, env=env)
        if runner == "go":
            return self._run_simple(["go", "test", *test_paths], runner="go", env=env)
        if runner == "dotnet":
            return self._run_simple(["dotnet", "test", *test_paths], runner="dotnet", env=env)
        if runner == "mvn":
            return self._run_simple(["mvn", "test"], runner="mvn", env=env)
        if runner == "gradle":
            return self._run_simple(["gradle", "test"], runner="gradle", env=env)

        # Fallback: pytest
        return self._run_pytest(test_paths, extra_args=extra_args, env=env)

    def _run_pytest(
        self,
        test_paths: list[str],
        *,
        extra_args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> TestRunResult:
        # Validate paths stay inside repo
        safe_paths: list[str] = []
        for p in test_paths:
            full = (self.root / p).resolve()
            if not str(full).startswith(str(self.root)):
                logger.warning("Skipping path outside repo: %s", p)
                continue
            if full.exists():
                safe_paths.append(p)
            else:
                # Still pass relative path; pytest may resolve via collection
                safe_paths.append(p)

        if not safe_paths:
            return TestRunResult(
                command=[],
                exit_code=0,
                metadata={"reason": "no_valid_test_paths"},
                runner="pytest",
            )

        with tempfile.TemporaryDirectory(prefix="qgate-pytest-") as tmp:
            report_path = Path(tmp) / "report.json"
            cmd = [
                "python",
                "-m",
                "pytest",
                *safe_paths,
                "-q",
                "--tb=short",
                f"--json-report",
                f"--json-report-file={report_path}",
            ]
            # json-report plugin may be missing — try without first path variant
            extra_args = extra_args or []
            cmd_simple = [
                "python",
                "-m",
                "pytest",
                *safe_paths,
                "-q",
                "--tb=short",
                *extra_args,
            ]

            # Prefer simple invocation (no plugin dependency)
            return self._execute(cmd_simple, runner="pytest", env=env, parse_pytest=True)

    def _run_simple(
        self,
        cmd: list[str],
        *,
        runner: str,
        env: dict[str, str] | None = None,
    ) -> TestRunResult:
        return self._execute(cmd, runner=runner, env=env, parse_pytest=False)

    def _execute(
        self,
        cmd: list[str],
        *,
        runner: str,
        env: dict[str, str] | None = None,
        parse_pytest: bool = False,
    ) -> TestRunResult:
        # Final safety: first token must be allowlisted binary name
        binary = cmd[0]
        allowed_bins = {"python", "pytest", "npm", "npx", "mvn", "gradle", "go", "dotnet"}
        if binary not in allowed_bins:
            raise PermissionError(f"Binary '{binary}' not allowed")

        run_env = os.environ.copy()
        if env:
            run_env.update(env)
        run_env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
        # Prevent pytest from picking up outer configs unexpectedly
        run_env.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "0")

        start = time.perf_counter()
        timed_out = False
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                env=run_env,
                check=False,
            )
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
            exit_code = proc.returncode
        except subprocess.TimeoutExpired as e:
            timed_out = True
            stdout = (e.stdout or b"").decode("utf-8", errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
            stderr = (e.stderr or b"").decode("utf-8", errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
            exit_code = 124
        except FileNotFoundError as e:
            return TestRunResult(
                command=cmd,
                exit_code=127,
                stderr=str(e),
                runner=runner,
                metadata={"error": "runner_not_found"},
            )

        duration = time.perf_counter() - start
        result = TestRunResult(
            command=cmd,
            exit_code=exit_code,
            duration_s=round(duration, 3),
            stdout=stdout[-50_000:],
            stderr=stderr[-20_000:],
            runner=runner,
            timed_out=timed_out,
        )

        if parse_pytest:
            self._parse_pytest_output(result)
        else:
            # Generic: treat non-zero as failure
            if exit_code == 0:
                result.passed = 1
                result.executed = 1
            else:
                result.failed = 1
                result.executed = 1

        return result

    def _parse_pytest_output(self, result: TestRunResult) -> None:
        """Parse pytest -q summary line: 'N passed, M failed, K skipped'."""
        text = result.stdout + "\n" + result.stderr
        # Summary patterns
        passed = _first_int(re.search(r"(\d+)\s+passed", text))
        failed = _first_int(re.search(r"(\d+)\s+failed", text))
        skipped = _first_int(re.search(r"(\d+)\s+skipped", text))
        errors = _first_int(re.search(r"(\d+)\s+error", text))

        result.passed = passed
        result.failed = failed
        result.skipped = skipped
        result.errors = errors
        result.executed = passed + failed + errors

        # Extract FAILURES section snippets
        tests: list[IndividualTestResult] = []
        # Lines like: FAILED tests/test_foo.py::test_bar - AssertionError
        for m in re.finditer(r"FAILED\s+(\S+)\s*-?\s*(.*)$", text, re.MULTILINE):
            nodeid = m.group(1).strip()
            msg = (m.group(2) or "").strip()
            file_path = nodeid.split("::")[0] if "::" in nodeid else nodeid
            tests.append(
                IndividualTestResult(
                    nodeid=nodeid,
                    status=TestStatus.FAILED,
                    message=msg[:1000],
                    traceback=_extract_traceback_for(nodeid, text)[:3000],
                    file_path=file_path,
                )
            )
        for m in re.finditer(r"ERROR\s+(\S+)", text):
            nodeid = m.group(1).strip()
            tests.append(
                IndividualTestResult(
                    nodeid=nodeid,
                    status=TestStatus.ERROR,
                    message="collection/runtime error",
                    traceback=_extract_traceback_for(nodeid, text)[:3000],
                )
            )
        result.tests = tests

        # If summary missing but exit 0
        if result.executed == 0 and result.exit_code == 0 and "passed" not in text.lower():
            # Might be no tests collected
            if "no tests ran" in text.lower() or "collected 0" in text.lower():
                result.metadata["no_tests_collected"] = True


def _first_int(m: re.Match[str] | None) -> int:
    if not m:
        return 0
    try:
        return int(m.group(1))
    except (ValueError, IndexError):
        return 0


def _extract_traceback_for(nodeid: str, text: str) -> str:
    # Best-effort: find nodeid near a traceback
    idx = text.find(nodeid)
    if idx < 0:
        return ""
    snippet = text[max(0, idx - 200) : idx + 1500]
    return snippet
