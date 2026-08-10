"""Tests for safe test runner."""

from pathlib import Path

from tools.testing.runner import TestRunner


def test_empty_selection(tmp_path: Path):
    runner = TestRunner(tmp_path)
    result = runner.run([])
    assert result.executed == 0
    assert result.exit_code == 0


def test_pytest_pass(tmp_path: Path):
    test_file = tmp_path / "test_ok.py"
    test_file.write_text("def test_yes():\n    assert 1 + 1 == 2\n", encoding="utf-8")
    runner = TestRunner(tmp_path, timeout_seconds=30)
    result = runner.run(["test_ok.py"], runner="pytest")
    assert result.failed == 0
    assert result.passed >= 1
    assert result.exit_code == 0


def test_pytest_fail(tmp_path: Path):
    test_file = tmp_path / "test_bad.py"
    test_file.write_text("def test_no():\n    assert 1 + 1 == 3\n", encoding="utf-8")
    runner = TestRunner(tmp_path, timeout_seconds=30)
    result = runner.run(["test_bad.py"], runner="pytest")
    assert result.failed >= 1
    assert result.exit_code != 0
    assert any(t.status.value == "failed" for t in result.tests) or result.failed >= 1


def test_disallow_unknown_runner(tmp_path: Path):
    runner = TestRunner(tmp_path, allowlist=["pytest"])
    try:
        runner.run(["x"], runner="rm")
        assert False, "should have raised"
    except PermissionError:
        pass
