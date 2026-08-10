"""Tests for test impact selection."""

from pathlib import Path

from tools.testing.impact import TestImpactAnalyzer


def test_p0_stem_match(tmp_path: Path):
    analyzer = TestImpactAnalyzer(tmp_path)
    result = analyzer.select(
        changed_files=["src/payment/service.py"],
        all_tests=[
            "tests/payment/test_service.py",
            "tests/user/test_profile.py",
            "tests/payment/test_checkout.py",
        ],
    )
    assert "tests/payment/test_service.py" in result["p0"] or "tests/payment/test_service.py" in result["p1"]
    assert "tests/payment/test_service.py" in result["tests_to_execute"] or result["p1"]


def test_no_tests():
    analyzer = TestImpactAnalyzer(".")
    result = analyzer.select(changed_files=["README.md"], all_tests=[])
    assert result["tests_to_execute"] == []
    assert result["total_discovered"] == 0
