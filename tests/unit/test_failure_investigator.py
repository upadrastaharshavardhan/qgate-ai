"""Tests for failure classification."""

from agents.failure_investigator.agent import failure_investigator_node
from core.models.testing import FailureClass


def test_real_regression_when_source_and_assert():
    state = {
        "repository_path": ".",
        "test_results": {
            "failed": 1,
            "errors": 0,
            "failed_tests": [
                {
                    "nodeid": "tests/test_payment.py::test_fee",
                    "message": "AssertionError: expected 10 got 12",
                    "traceback": "assert 12 == 10",
                }
            ],
        },
        "changed_files": ["src/payment/service.py"],
        "changed_symbols": [{"name": "calculate_fee", "file_path": "src/payment/service.py"}],
        "git_diff_summary": "def calculate_fee",
        "audit_events": [],
        "execution_timeline": {},
        "regression_findings": [],
        "historical_context": {},
    }
    out = failure_investigator_node(state)  # type: ignore[arg-type]
    inv = out["historical_context"]["failure_investigations"]
    assert len(inv) == 1
    assert inv[0]["classification"] == FailureClass.REAL_REGRESSION.value


def test_dependency_failure():
    state = {
        "repository_path": ".",
        "test_results": {
            "failed": 0,
            "errors": 1,
            "failed_tests": [
                {
                    "nodeid": "tests/test_x.py::test_y",
                    "message": "ModuleNotFoundError: No module named 'foo'",
                    "traceback": "ImportError",
                }
            ],
        },
        "changed_files": ["requirements.txt"],
        "changed_symbols": [],
        "git_diff_summary": "",
        "audit_events": [],
        "execution_timeline": {},
        "regression_findings": [],
        "historical_context": {},
    }
    out = failure_investigator_node(state)  # type: ignore[arg-type]
    inv = out["historical_context"]["failure_investigations"]
    assert inv[0]["classification"] == FailureClass.DEPENDENCY_FAILURE.value


def test_skip_when_no_failures():
    state = {
        "repository_path": ".",
        "test_results": {"failed": 0, "errors": 0},
        "regression_findings": [],
    }
    out = failure_investigator_node(state)  # type: ignore[arg-type]
    assert out["phase"] == "failure_investigator_skipped"
