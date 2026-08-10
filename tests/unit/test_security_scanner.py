"""Tests for deterministic security scanner."""

from pathlib import Path

from tools.security.scanner import SecurityScanner


def test_detects_hardcoded_password(tmp_path: Path):
    src = tmp_path / "app.py"
    src.write_text('password = "secret123"\nprint(password)\n', encoding="utf-8")
    scanner = SecurityScanner(tmp_path)
    findings = scanner.scan_files(["app.py"])
    assert any("password" in f.title.lower() or "secret" in f.title.lower() for f in findings)
    assert any(f.severity.value == "critical" for f in findings)


def test_clean_file(tmp_path: Path):
    src = tmp_path / "ok.py"
    src.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    scanner = SecurityScanner(tmp_path)
    findings = scanner.scan_files(["ok.py"])
    assert findings == []
