"""Tests for quality memory store."""

from pathlib import Path

from core.memory.store import MemoryStore, reset_memory_store


def test_record_and_historical_context(tmp_path: Path):
    reset_memory_store()
    db = tmp_path / "mem.db"
    store = MemoryStore(f"sqlite:///{db}")

    store.record_analysis(
        repository_path=str(tmp_path),
        base_commit="aaa",
        head_commit="bbb",
        decision="BLOCK",
        quality_score=50,
        risk_score=80,
        confidence=0.9,
        changed_files=["src/payment.py"],
        tests_failed=1,
        tests_executed=1,
        final_reason="regression",
    )
    store.record_test_failures(
        repository_path=str(tmp_path),
        head_commit="bbb",
        investigations=[
            {
                "test_nodeid": "tests/test_payment.py::test_fee",
                "classification": "REAL_REGRESSION",
                "related_changed_files": ["src/payment.py"],
                "rationale": "fee broke",
            }
        ],
    )

    ctx = store.get_historical_context(str(tmp_path), changed_files=["src/payment.py"])
    assert ctx["analysis_count"] >= 1
    assert ctx["failure_rate"] >= 0.9
    assert any(h["file_path"] == "src/payment.py" for h in ctx["hotspots"])
    assert any(s["test_nodeid"].startswith("tests/test_payment") for s in ctx["similar_failures"])

    rel = store.get_test_relevance(str(tmp_path), ["src/payment.py"])
    assert "tests/test_payment.py::test_fee" in rel


def test_false_positive_suppression(tmp_path: Path):
    reset_memory_store()
    db = tmp_path / "mem2.db"
    store = MemoryStore(f"sqlite:///{db}")
    store.record_findings(
        repository_path=str(tmp_path),
        head_commit="c1",
        findings=[
            {
                "category": "security",
                "severity": "critical",
                "title": "Hardcoded password assignment",
                "impacted_files": ["app.py"],
                "status": "new",
            }
        ],
    )
    # mark FP via fingerprint from second record path
    from core.memory.store import _finding_fingerprint

    fp = _finding_fingerprint("security", "Hardcoded password assignment", ["app.py"])
    assert store.mark_finding_status(str(tmp_path), fp, "false_positive")
    ctx = store.get_historical_context(str(tmp_path))
    assert any(s["status"] == "false_positive" for s in ctx["suppressed_findings"])
