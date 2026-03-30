"""Runtime validation helpers for storage, queueing, and optional capabilities."""

from __future__ import annotations

import os
import shutil
import sqlite3
from pathlib import Path

import background_jobs
import db
import ingest


def _write_probe(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("ok", encoding="utf-8")
    path.unlink(missing_ok=True)


def _check_writable_dir(path: Path) -> tuple[bool, str]:
    try:
        path.mkdir(parents=True, exist_ok=True)
        _write_probe(path / ".secondbrain-write-check")
        return True, f"{path} is writable."
    except Exception as exc:
        return False, f"{path} is not writable: {exc}"


def _check_sqlite(db_path: Path) -> tuple[bool, str]:
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path), timeout=10)
        try:
            result = conn.execute("PRAGMA quick_check").fetchone()
        finally:
            conn.close()
        if result and result[0] == "ok":
            return True, f"SQLite metadata is healthy at {db_path}."
        return False, f"SQLite quick_check returned {result[0] if result else 'no result'}."
    except Exception as exc:
        return False, f"SQLite metadata check failed: {exc}"


def _check_ocr() -> tuple[str, str]:
    try:
        import pdf2image  # noqa: F401
        import pytesseract  # noqa: F401
    except Exception as exc:
        return "warning", f"OCR Python packages are unavailable: {exc}"

    missing = []
    if shutil.which("tesseract") is None:
        missing.append("tesseract")
    if shutil.which("pdftoppm") is None and shutil.which("pdftocairo") is None:
        missing.append("poppler")
    if missing:
        return "warning", f"OCR is optional and currently incomplete: missing {', '.join(missing)}."
    return "pass", "OCR dependencies are installed and available."


def collect_system_status(
    *,
    db_path: Path | None = None,
    chroma_path: Path | None = None,
    upload_dir: Path | None = None,
) -> dict:
    """Collect runtime checks used by the UI and API health endpoint."""
    metadata_db = Path(db_path or db.DB_PATH)
    vector_dir = Path(chroma_path or ingest.CHROMA_PATH)
    jobs_upload_dir = Path(upload_dir or background_jobs.UPLOAD_DIR)

    checks: list[dict] = []

    def add_check(
        *,
        key: str,
        label: str,
        status: str,
        detail: str,
        required: bool = True,
        hint: str | None = None,
    ) -> None:
        checks.append(
            {
                "key": key,
                "label": label,
                "status": status,
                "detail": detail,
                "required": required,
                "hint": hint,
            }
        )

    db_ok, db_detail = _check_sqlite(metadata_db)
    add_check(
        key="sqlite",
        label="Metadata database",
        status="pass" if db_ok else "fail",
        detail=db_detail,
        hint="Keep the data directory on persistent disk.",
    )

    chroma_ok, chroma_detail = _check_writable_dir(vector_dir)
    add_check(
        key="chroma",
        label="Vector store directory",
        status="pass" if chroma_ok else "fail",
        detail=chroma_detail,
        hint="Mount the data directory as a Docker volume if you deploy in containers.",
    )

    uploads_ok, uploads_detail = _check_writable_dir(jobs_upload_dir)
    add_check(
        key="uploads",
        label="Background job uploads",
        status="pass" if uploads_ok else "fail",
        detail=uploads_detail,
        hint="Queued file ingestion depends on this directory being writable.",
    )

    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    add_check(
        key="anthropic",
        label="Anthropic API key",
        status="pass" if api_key else "fail",
        detail="Anthropic API key is configured." if api_key else "ANTHROPIC_API_KEY is not configured.",
        hint="Add the key to .env or your deployment secrets before using answers, summaries, tagging, or evaluation.",
    )

    worker_state = background_jobs.embedded_worker_status()
    worker_status = "pass" if worker_state == "online" else "warning"
    worker_detail = {
        "online": "Embedded worker is online.",
        "disabled": "Embedded worker is disabled.",
        "starting": "Embedded worker is still starting.",
    }.get(worker_state, f"Embedded worker reported {worker_state}.")
    add_check(
        key="worker",
        label="Background worker",
        status=worker_status,
        detail=worker_detail,
        required=False,
        hint="For durable ingestion outside the Streamlit process, run worker.py or the Docker worker service.",
    )

    ocr_status, ocr_detail = _check_ocr()
    add_check(
        key="ocr",
        label="OCR support",
        status=ocr_status,
        detail=ocr_detail,
        required=False,
        hint="OCR is only needed for scanned PDFs.",
    )

    try:
        workspace_count = len(db.get_workspaces())
        add_check(
            key="workspaces",
            label="Workspace registry",
            status="pass",
            detail=f"{workspace_count} persisted workspace(s) registered.",
            required=False,
        )
    except Exception as exc:
        add_check(
            key="workspaces",
            label="Workspace registry",
            status="fail",
            detail=f"Workspace registry check failed: {exc}",
            hint="The UI relies on the workspace registry to keep empty workspaces visible.",
        )

    failed = sum(1 for check in checks if check["status"] == "fail")
    warnings = sum(1 for check in checks if check["status"] == "warning")
    passed = sum(1 for check in checks if check["status"] == "pass")

    if failed:
        status = "fail"
    elif warnings:
        status = "degraded"
    else:
        status = "ok"

    return {
        "status": status,
        "summary": {
            "passed": passed,
            "warnings": warnings,
            "failed": failed,
            "total": len(checks),
        },
        "checks": checks,
        "paths": {
            "data_dir": str(metadata_db.parent),
            "metadata_db": str(metadata_db),
            "chroma_dir": str(vector_dir),
            "job_uploads_dir": str(jobs_upload_dir),
        },
        "persistence": {
            "mode": "local-disk",
            "detail": (
                "SecondBrain persists metadata in SQLite and embeddings on local disk. "
                "Retention depends on keeping the data directory between restarts."
            ),
        },
    }
