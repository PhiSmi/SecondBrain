"""Persisted background job queue for non-blocking ingestion."""

from __future__ import annotations

import logging
import re
import threading
import time
import uuid
from pathlib import Path

import db
import ingest
import query

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(__file__).parent / "data" / "job_uploads"
POLL_INTERVAL_SECONDS = 1.5

_worker_lock = threading.Lock()
_worker_thread: threading.Thread | None = None


def ensure_worker_running() -> None:
    """Start the background worker once per process."""
    global _worker_thread
    with _worker_lock:
        if _worker_thread is not None and _worker_thread.is_alive():
            return
        _worker_thread = threading.Thread(
            target=_worker_loop,
            name="secondbrain-ingest-worker",
            daemon=True,
        )
        _worker_thread.start()
        logger.info("Started background ingest worker")


def worker_is_running() -> bool:
    return _worker_thread is not None and _worker_thread.is_alive()


def queue_text_ingest(
    text: str,
    title: str,
    tags: list[str] | None = None,
    workspace: str = "default",
    embed_model_id: str | None = None,
    auto_tag: bool = False,
) -> int:
    ensure_worker_running()
    return db.create_ingest_job(
        "text",
        title=title,
        workspace=workspace,
        payload={
            "text": text,
            "title": title,
            "tags": tags or [],
            "workspace": workspace,
            "embed_model_id": embed_model_id,
            "auto_tag": auto_tag,
        },
    )


def queue_url_ingest(
    url: str,
    title: str | None = None,
    tags: list[str] | None = None,
    workspace: str = "default",
    embed_model_id: str | None = None,
    auto_tag: bool = False,
) -> int:
    ensure_worker_running()
    job_title = title or url
    return db.create_ingest_job(
        "url",
        title=job_title,
        workspace=workspace,
        payload={
            "url": url,
            "title": title,
            "tags": tags or [],
            "workspace": workspace,
            "embed_model_id": embed_model_id,
            "auto_tag": auto_tag,
        },
    )


def queue_file_ingest(
    file_bytes: bytes,
    filename: str,
    title: str,
    tags: list[str] | None = None,
    workspace: str = "default",
    embed_model_id: str | None = None,
    ocr: bool = False,
    auto_tag: bool = False,
) -> int:
    ensure_worker_running()
    file_path = _write_upload(file_bytes, filename)
    try:
        return db.create_ingest_job(
            "file",
            title=title,
            workspace=workspace,
            payload={
                "path": str(file_path),
                "filename": filename,
                "title": title,
                "tags": tags or [],
                "workspace": workspace,
                "embed_model_id": embed_model_id,
                "ocr": ocr,
                "auto_tag": auto_tag,
            },
        )
    except Exception:
        file_path.unlink(missing_ok=True)
        raise


def queue_youtube_ingest(
    url: str,
    title: str | None = None,
    tags: list[str] | None = None,
    workspace: str = "default",
    embed_model_id: str | None = None,
    auto_tag: bool = False,
) -> int:
    ensure_worker_running()
    job_title = title or url
    return db.create_ingest_job(
        "youtube",
        title=job_title,
        workspace=workspace,
        payload={
            "url": url,
            "title": title,
            "tags": tags or [],
            "workspace": workspace,
            "embed_model_id": embed_model_id,
            "auto_tag": auto_tag,
        },
    )


def queue_bulk_url_ingest(
    urls: list[str],
    tags: list[str] | None = None,
    workspace: str = "default",
    embed_model_id: str | None = None,
    auto_tag: bool = False,
) -> int:
    clean_urls = [url.strip() for url in urls if url.strip()]
    if not clean_urls:
        raise ValueError("At least one URL is required")
    ensure_worker_running()
    return db.create_ingest_job(
        "bulk_urls",
        title=f"Bulk URL ingest ({len(clean_urls)} URLs)",
        workspace=workspace,
        payload={
            "urls": clean_urls,
            "tags": tags or [],
            "workspace": workspace,
            "embed_model_id": embed_model_id,
            "auto_tag": auto_tag,
        },
    )


def list_jobs(limit: int = 20, workspace: str | None = None) -> list[dict]:
    ensure_worker_running()
    return db.get_ingest_jobs(limit=limit, workspace=workspace)


def get_job(job_id: int) -> dict | None:
    ensure_worker_running()
    return db.get_ingest_job(job_id)


def cancel_job(job_id: int) -> bool:
    job = db.get_ingest_job(job_id)
    if job is None:
        return False
    cancelled = db.cancel_ingest_job(job_id)
    if cancelled:
        _cleanup_job_artifacts(job)
    return cancelled


def _worker_loop() -> None:
    while True:
        job = db.claim_next_ingest_job()
        if job is None:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        try:
            result = _process_job(job)
        except Exception as exc:
            logger.exception("Background ingest job %s failed", job["id"])
            db.fail_ingest_job(job["id"], str(exc))
        else:
            db.complete_ingest_job(job["id"], result)
        finally:
            _cleanup_job_artifacts(job)


def _process_job(job: dict) -> dict:
    payload = job["payload"]
    workspace = payload.get("workspace") or job["workspace"]

    if job["job_type"] == "text":
        tags = _resolve_tags(
            payload.get("text", ""),
            payload.get("tags"),
            workspace=workspace,
            auto_tag=payload.get("auto_tag", False),
        )
        chunks = ingest.ingest_text(
            payload["text"],
            title=payload["title"],
            tags=tags,
            workspace=workspace,
            embed_model_id=payload.get("embed_model_id"),
        )
        return {"chunks": chunks, "tags": tags}

    if job["job_type"] == "url":
        return _process_url_job(payload, workspace)

    if job["job_type"] == "file":
        path = Path(payload["path"])
        file_bytes = path.read_bytes()
        text, source_type = ingest.extract_file_text(
            file_bytes,
            payload["filename"],
            ocr=payload.get("ocr", False),
        )
        tags = _resolve_tags(
            text,
            payload.get("tags"),
            workspace=workspace,
            auto_tag=payload.get("auto_tag", False),
        )
        chunks = ingest.ingest_text(
            text,
            title=payload["title"],
            source_type=source_type,
            tags=tags,
            workspace=workspace,
            embed_model_id=payload.get("embed_model_id"),
        )
        return {"chunks": chunks, "tags": tags, "source_type": source_type}

    if job["job_type"] == "youtube":
        transcript = ingest.fetch_youtube_transcript(payload["url"])
        tags = _resolve_tags(
            transcript,
            payload.get("tags"),
            workspace=workspace,
            auto_tag=payload.get("auto_tag", False),
        )
        chunks = ingest.ingest_text(
            transcript,
            title=payload.get("title") or payload["url"],
            source_type="youtube",
            url=payload["url"],
            tags=tags,
            workspace=workspace,
            embed_model_id=payload.get("embed_model_id"),
        )
        return {"chunks": chunks, "tags": tags}

    if job["job_type"] == "bulk_urls":
        results = []
        succeeded = 0
        for url in payload.get("urls", []):
            try:
                result = _process_url_job(
                    {
                        "url": url,
                        "title": url,
                        "tags": payload.get("tags"),
                        "workspace": workspace,
                        "embed_model_id": payload.get("embed_model_id"),
                        "auto_tag": payload.get("auto_tag", False),
                    },
                    workspace,
                )
                results.append({"url": url, "chunks": result["chunks"], "warning": result["warning"]})
                succeeded += 1
            except Exception as exc:
                results.append({"url": url, "error": str(exc)})
        return {"total_urls": len(payload.get("urls", [])), "succeeded": succeeded, "results": results}

    raise ValueError(f"Unsupported background ingest job type: {job['job_type']}")


def _process_url_job(payload: dict, workspace: str) -> dict:
    text, js_warning = ingest.fetch_url_text(payload["url"])
    tags = _resolve_tags(
        text,
        payload.get("tags"),
        workspace=workspace,
        auto_tag=payload.get("auto_tag", False),
    )
    chunks = ingest.ingest_text(
        text,
        title=payload.get("title") or payload["url"],
        source_type="url",
        url=payload["url"],
        tags=tags,
        workspace=workspace,
        embed_model_id=payload.get("embed_model_id"),
    )
    return {"chunks": chunks, "warning": js_warning, "tags": tags}


def _resolve_tags(
    text: str,
    tags: list[str] | None,
    *,
    workspace: str,
    auto_tag: bool,
) -> list[str]:
    if tags:
        return tags
    if auto_tag and text.strip():
        return query.suggest_tags(text, workspace=workspace)
    return []


def _write_upload(file_bytes: bytes, filename: str) -> Path:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(filename).name).strip("._") or "upload.bin"
    path = UPLOAD_DIR / f"{uuid.uuid4().hex}_{safe_name}"
    path.write_bytes(file_bytes)
    return path


def _cleanup_job_artifacts(job: dict) -> None:
    if job["job_type"] != "file":
        return
    path = job["payload"].get("path")
    if not path:
        return
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        logger.warning("Failed to remove background job upload %s", path)
