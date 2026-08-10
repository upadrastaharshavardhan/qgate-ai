"""Test execution and failure investigation models."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TestStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"
    FLAKY = "flaky"
    NOT_RUN = "not_run"


class FailureClass(str, Enum):
    REAL_REGRESSION = "REAL_REGRESSION"
    TEST_DEFECT = "TEST_DEFECT"
    ENVIRONMENT_FAILURE = "ENVIRONMENT_FAILURE"
    FLAKY_TEST = "FLAKY_TEST"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
    UNKNOWN = "UNKNOWN"


class IndividualTestResult(BaseModel):
    nodeid: str
    status: TestStatus
    duration_s: float = 0.0
    message: str = ""
    traceback: str = ""
    file_path: str | None = None
    line: int | None = None


class TestRunResult(BaseModel):
    """Aggregated result of a targeted test run."""

    command: list[str] = Field(default_factory=list)
    exit_code: int = 0
    duration_s: float = 0.0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    executed: int = 0
    stdout: str = ""
    stderr: str = ""
    tests: list[IndividualTestResult] = Field(default_factory=list)
    runner: str = "pytest"
    timed_out: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_summary_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "exit_code": self.exit_code,
            "duration_s": self.duration_s,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "errors": self.errors,
            "executed": self.executed,
            "runner": self.runner,
            "timed_out": self.timed_out,
            "failed_tests": [
                {
                    "nodeid": t.nodeid,
                    "message": t.message[:500],
                    "traceback": t.traceback[:2000],
                }
                for t in self.tests
                if t.status in {TestStatus.FAILED, TestStatus.ERROR}
            ],
        }


class FailureInvestigation(BaseModel):
    test_nodeid: str
    classification: FailureClass
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    rationale: str = ""
    related_changed_files: list[str] = Field(default_factory=list)
    related_symbols: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    recommendation: str = ""
