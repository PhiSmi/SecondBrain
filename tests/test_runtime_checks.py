"""Tests for runtime validation helpers."""

from pathlib import Path

import runtime_checks


def test_collect_system_status_ok(tmp_path, monkeypatch):
    db_path = tmp_path / "metadata.db"
    chroma_path = tmp_path / "chroma"
    upload_path = tmp_path / "uploads"

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(runtime_checks.background_jobs, "embedded_worker_status", lambda: "online")
    monkeypatch.setattr(runtime_checks, "_check_ocr", lambda: ("pass", "OCR ready."))
    monkeypatch.setattr(runtime_checks.db, "get_workspaces", lambda: ["default", "research"])

    status = runtime_checks.collect_system_status(
        db_path=db_path,
        chroma_path=chroma_path,
        upload_dir=upload_path,
    )

    assert status["status"] == "ok"
    assert status["summary"]["failed"] == 0
    assert status["summary"]["warnings"] == 0
    assert Path(status["paths"]["metadata_db"]) == db_path
    assert Path(status["paths"]["chroma_dir"]) == chroma_path


def test_collect_system_status_fails_without_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(runtime_checks.background_jobs, "embedded_worker_status", lambda: "online")
    monkeypatch.setattr(runtime_checks, "_check_ocr", lambda: ("pass", "OCR ready."))
    monkeypatch.setattr(runtime_checks.db, "get_workspaces", lambda: ["default"])

    status = runtime_checks.collect_system_status(
        db_path=tmp_path / "metadata.db",
        chroma_path=tmp_path / "chroma",
        upload_dir=tmp_path / "uploads",
    )

    assert status["status"] == "fail"
    anthropic_check = next(check for check in status["checks"] if check["key"] == "anthropic")
    assert anthropic_check["status"] == "fail"
