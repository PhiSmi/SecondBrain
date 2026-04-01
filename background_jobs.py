"""Persisted background job queue for non-blocking ingestion."""

from __future__ import annotations

import logging
import os
import re
import socket
import threading
import time
import uuid
from pathlib import Path

import config
import db
import ingest
import query

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(__file__).parent / "data" / "job_uploads"
DEFAULT_STAGE_TOTAL = 4

_worker_lock = threading.Lock()
_worker_thread: threading.Thread | None = None
_embedded_worker_id: str | None = None


class JobCancelled(Exception):
    """Raised when a queued job is cancelled while being processed."""


def _jobs_setting(key: str, default):
    return config.jobs().get(key, default)


def _poll_interval_seconds() -> float:
    return float(_jobs_setting("poll_interval_seconds", 1.5))


def _lease_seconds() -> int:
    return int(_jobs_setting("lease_seconds", 1800))


def embedded_worker_enabled() -> bool:
    raw = os.getenv("SECOND_BRAIN_EMBEDDED_WORKER")
    if raw is not None:
        return raw.strip().lower() not in {"0", "false", "no", "off"}
    return bool(_jobs_setting("embedded_worker", True))


def ensure_worker_running() -> bool:
    """Start the embedded background worker once per process when enabled."""
    global _worker_thread, _embedded_worker_id
    if not embedded_worker_enabled():
        return False

    with _worker_lock:
        if _worker_thread is not None and _worker_thread.is_alive():
            return True
        _embedded_worker_id = _embedded_worker_id or _build_worker_id("embedded")
        _worker_thread = threading.Thread(
            target=run_worker_forever,
            kwargs={"worker_id": _embedded_worker_id},
            name="secondbrain-ingest-worker",
            daemon=True,
        )
        _worker_thread.start()
        logger.info("Started embedded background ingest worker %s", _embedded_worker_id)
        return True


def worker_is_running() -> bool:
    return _worker_thread is not None and _worker_thread.is_alive()


def embedded_worker_status() -> str:
    if not embedded_worker_enabled():
        return "disabled"
    if worker_is_running():
        return "online"
    return "starting"


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
        progress_total=DEFAULT_STAGE_TOTAL,
        progress_message="Queued",
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
        progress_total=DEFAULT_STAGE_TOTAL,
        progress_message="Queued",
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
            progress_total=DEFAULT_STAGE_TOTAL,
            progress_message="Queued",
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
        progress_total=DEFAULT_STAGE_TOTAL,
        progress_message="Queued",
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
        progress_total=len(clean_urls),
        progress_message="Queued",
        payload={
            "urls": clean_urls,
            "tags": tags or [],
            "workspace": workspace,
            "embed_model_id": embed_model_id,
            "auto_tag": auto_tag,
        },
    )


def list_jobs(limit: int = 20, workspace: str | None = None) -> list[dict]:
    return db.get_ingest_jobs(limit=limit, workspace=workspace)


def get_job(job_id: int) -> dict | None:
    return db.get_ingest_job(job_id)


def cancel_job(job_id: int) -> str | None:
    job = db.get_ingest_job(job_id)
    if job is None:
        return None
    status = db.cancel_ingest_job(job_id)
    if status == "cancelled":
        _cleanup_job_artifacts(job)
    return status


def process_next_job(worker_id: str | None = None) -> dict | None:
    active_worker_id = worker_id or _build_worker_id("worker")
    job = db.claim_next_ingest_job(active_worker_id, _lease_seconds())
    if job is None:
        return None

    try:
        result = _process_job(job)
    except JobCancelled:
        logger.info("Background ingest job %s cancelled", job["id"])
        db.mark_ingest_job_cancelled(job["id"], active_worker_id)
        result = None
    except Exception as exc:
        logger.exception("Background ingest job %s failed", job["id"])
        db.fail_ingest_job(job["id"], str(exc))
        result = None
    else:
        db.complete_ingest_job(job["id"], result)
    finally:
        _cleanup_job_artifacts(job)

    return db.get_ingest_job(job["id"])


def run_worker_forever(worker_id: str | None = None) -> None:
    active_worker_id = worker_id or _build_worker_id("worker")
    logger.info("Worker %s polling every %.1fs", active_worker_id, _poll_interval_seconds())
    while True:
        try:
            job = process_next_job(active_worker_id)
            if job is None:
                time.sleep(_poll_interval_seconds())
        except Exception:
            logger.exception("Worker %s encountered an unexpected error; continuing after cooldown", active_worker_id)
            time.sleep(_poll_interval_seconds() * 2)


def _process_job(job: dict) -> dict:
    existing_source = db.get_source_by_ingest_job(job["id"])
    if existing_source and job["job_type"] != "bulk_urls":
        return {
            "chunks": existing_source["chunk_count"],
            "source_id": existing_source["id"],
            "recovered": True,
        }

    payload = job["payload"]
    workspace = payload.get("workspace") or job["workspace"]

    if job["job_type"] == "text":
        _set_job_progress(job, 1, "Preparing text import")
        tags = _resolve_tags(
            job,
            payload.get("text", ""),
            payload.get("tags"),
            workspace=workspace,
            auto_tag=payload.get("auto_tag", False),
            progress_step=2,
            progress_message="Suggesting tags",
        )
        _set_job_progress(job, 3, "Chunking and embedding")
        chunks = ingest.ingest_text(
            payload["text"],
            title=payload["title"],
            tags=tags,
            workspace=workspace,
            embed_model_id=payload.get("embed_model_id"),
            ingest_job_id=job["id"],
        )
        source = db.get_source_by_ingest_job(job["id"])
        return {"chunks": chunks, "tags": tags, "source_id": source["id"] if source else None}

    if job["job_type"] == "url":
        return _process_url_job(job, payload, workspace)

    if job["job_type"] == "file":
        _set_job_progress(job, 1, "Reading uploaded file")
        path = Path(payload["path"])
        file_bytes = path.read_bytes()
        _set_job_progress(job, 2, "Extracting text")
        text, source_type = ingest.extract_file_text(
            file_bytes,
            payload["filename"],
            ocr=payload.get("ocr", False),
        )
        tags = _resolve_tags(
            job,
            text,
            payload.get("tags"),
            workspace=workspace,
            auto_tag=payload.get("auto_tag", False),
            progress_step=3,
            progress_message="Suggesting tags",
        )
        _set_job_progress(job, 3, "Chunking and embedding")
        chunks = ingest.ingest_text(
            text,
            title=payload["title"],
            source_type=source_type,
            tags=tags,
            workspace=workspace,
            embed_model_id=payload.get("embed_model_id"),
            ingest_job_id=job["id"],
        )
        source = db.get_source_by_ingest_job(job["id"])
        return {
            "chunks": chunks,
            "tags": tags,
            "source_type": source_type,
            "source_id": source["id"] if source else None,
        }

    if job["job_type"] == "youtube":
        _set_job_progress(job, 1, "Fetching transcript")
        transcript = ingest.fetch_youtube_transcript(payload["url"])
        tags = _resolve_tags(
            job,
            transcript,
            payload.get("tags"),
            workspace=workspace,
            auto_tag=payload.get("auto_tag", False),
            progress_step=2,
            progress_message="Suggesting tags",
        )
        _set_job_progress(job, 3, "Chunking and embedding")
        chunks = ingest.ingest_text(
            transcript,
            title=payload.get("title") or payload["url"],
            source_type="youtube",
            url=payload["url"],
            tags=tags,
            workspace=workspace,
            embed_model_id=payload.get("embed_model_id"),
            ingest_job_id=job["id"],
        )
        source = db.get_source_by_ingest_job(job["id"])
        return {"chunks": chunks, "tags": tags, "source_id": source["id"] if source else None}

    if job["job_type"] == "bulk_urls":
        results = []
        total_urls = len(payload.get("urls", []))
        for idx, url in enumerate(payload.get("urls", []), 1):
            _set_job_progress(job, idx - 1, f"Fetching {url}")
            try:
                result = _process_url_job(
                    job,
                    {
                        "url": url,
                        "title": url,
                        "tags": payload.get("tags"),
                        "workspace": workspace,
                        "embed_model_id": payload.get("embed_model_id"),
                        "auto_tag": payload.get("auto_tag", False),
                    },
                    workspace,
                    use_stage_progress=False,
                )
                results.append({"url": url, "chunks": result["chunks"], "warning": result["warning"]})
            except JobCancelled:
                raise
            except Exception as exc:
                results.append({"url": url, "error": str(exc)})
            finally:
                _set_job_progress(job, idx, f"Processed {idx} of {total_urls} URLs")
        succeeded = sum(1 for result in results if not result.get("error"))
        return {"total_urls": total_urls, "succeeded": succeeded, "results": results}

    raise ValueError(f"Unsupported background ingest job type: {job['job_type']}")


def _process_url_job(job: dict, payload: dict, workspace: str, *, use_stage_progress: bool = True) -> dict:
    if use_stage_progress:
        _set_job_progress(job, 1, "Fetching URL content")
    else:
        _ensure_not_cancelled(job)
    text, js_warning = ingest.fetch_url_text(payload["url"])
    tags = _resolve_tags(
        job,
        text,
        payload.get("tags"),
        workspace=workspace,
        auto_tag=payload.get("auto_tag", False),
        progress_step=2,
        progress_message="Suggesting tags",
        update_progress=use_stage_progress,
    )
    if use_stage_progress:
        _set_job_progress(job, 3, "Chunking and embedding")
    else:
        _ensure_not_cancelled(job)
    chunks = ingest.ingest_text(
        text,
        title=payload.get("title") or payload["url"],
        source_type="url",
        url=payload["url"],
        tags=tags,
        workspace=workspace,
        embed_model_id=payload.get("embed_model_id"),
        ingest_job_id=None if job["job_type"] == "bulk_urls" else job["id"],
    )
    source = None if job["job_type"] == "bulk_urls" else db.get_source_by_ingest_job(job["id"])
    return {
        "chunks": chunks,
        "warning": js_warning,
        "tags": tags,
        "source_id": source["id"] if source else None,
    }


def _resolve_tags(
    job: dict,
    text: str,
    tags: list[str] | None,
    *,
    workspace: str,
    auto_tag: bool,
    progress_step: int,
    progress_message: str,
    update_progress: bool = True,
) -> list[str]:
    _ensure_not_cancelled(job)
    if tags:
        return tags
    if auto_tag and text.strip():
        if update_progress:
            _set_job_progress(job, progress_step, progress_message)
        return query.suggest_tags(text, workspace=workspace)
    return []


def _set_job_progress(job: dict, current: int, message: str) -> None:
    _ensure_not_cancelled(job)
    db.update_ingest_job_progress(
        job["id"],
        job["worker_id"],
        current,
        progress_message=message,
        lease_seconds=_lease_seconds(),
    )
    job["progress_current"] = current
    job["progress_message"] = message


def _ensure_not_cancelled(job: dict) -> None:
    if db.is_ingest_job_cancelling(job["id"], job["worker_id"]):
        raise JobCancelled()
    db.touch_ingest_job_lease(job["id"], job["worker_id"], _lease_seconds())


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


def _build_worker_id(prefix: str) -> str:
    host = socket.gethostname().split(".")[0]
    return f"{prefix}-{host}-{os.getpid()}"
