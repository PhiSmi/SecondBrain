"""SQLite metadata helpers for tracking ingested sources."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "metadata.db"
DEFAULT_EMBED_MODEL = "all-MiniLM-L6-v2"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    try:
        conn.execute(f"SELECT {column} FROM {table} LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _source_from_row(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    source = dict(row)
    source["tags"] = json.loads(source.get("tags") or "[]")
    if not source.get("embedding_model"):
        source["embedding_model"] = DEFAULT_EMBED_MODEL
    return source


def _job_from_row(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    job = dict(row)
    job["payload"] = json.loads(job.get("payload") or "{}")
    job["result"] = json.loads(job.get("result") or "{}")
    return job


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS sources (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT    NOT NULL,
            source_type TEXT    NOT NULL,
            url         TEXT,
            chunk_count INTEGER NOT NULL,
            tags        TEXT    NOT NULL DEFAULT '[]',
            workspace   TEXT    NOT NULL DEFAULT 'default',
            embedding_model TEXT NOT NULL DEFAULT 'all-MiniLM-L6-v2',
            ingest_job_id INTEGER,
            ingested_at TEXT    NOT NULL
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_sources_ingest_job
            ON sources(ingest_job_id)
            WHERE ingest_job_id IS NOT NULL;

        CREATE TABLE IF NOT EXISTS chunks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id   INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
            chroma_id   TEXT    NOT NULL,
            chunk_index INTEGER NOT NULL,
            text        TEXT    NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source_id);

        CREATE TABLE IF NOT EXISTS search_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            question    TEXT    NOT NULL,
            answer      TEXT    NOT NULL,
            sources     TEXT    NOT NULL DEFAULT '[]',
            tags_used   TEXT    NOT NULL DEFAULT '[]',
            workspace   TEXT    NOT NULL DEFAULT 'default',
            searched_at TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS api_usage (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id      TEXT    NOT NULL,
            operation     TEXT    NOT NULL,
            input_tokens  INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            cost_usd      REAL    NOT NULL DEFAULT 0.0,
            workspace     TEXT    NOT NULL DEFAULT 'default',
            created_at    TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS rss_feeds (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            url           TEXT    NOT NULL UNIQUE,
            title         TEXT,
            tags          TEXT    NOT NULL DEFAULT '[]',
            workspace     TEXT    NOT NULL DEFAULT 'default',
            last_fetched  TEXT,
            last_entry_id TEXT,
            active        INTEGER NOT NULL DEFAULT 1,
            created_at    TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS eval_pairs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            question        TEXT    NOT NULL,
            expected_answer TEXT    NOT NULL,
            tags            TEXT    NOT NULL DEFAULT '[]',
            workspace       TEXT    NOT NULL DEFAULT 'default',
            created_at      TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ingest_jobs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            job_type    TEXT    NOT NULL,
            title       TEXT    NOT NULL,
            workspace   TEXT    NOT NULL DEFAULT 'default',
            payload     TEXT    NOT NULL DEFAULT '{}',
            status      TEXT    NOT NULL DEFAULT 'pending',
            result      TEXT    NOT NULL DEFAULT '{}',
            error       TEXT,
            progress_current INTEGER NOT NULL DEFAULT 0,
            progress_total   INTEGER NOT NULL DEFAULT 0,
            progress_message TEXT,
            worker_id    TEXT,
            heartbeat_at TEXT,
            lease_expires_at TEXT,
            attempt_count INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT    NOT NULL,
            started_at  TEXT,
            finished_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_ingest_jobs_status_created
            ON ingest_jobs(status, created_at);
        """
    )
    _ensure_column(conn, "sources", "workspace", "TEXT NOT NULL DEFAULT 'default'")
    _ensure_column(conn, "sources", "embedding_model", f"TEXT NOT NULL DEFAULT '{DEFAULT_EMBED_MODEL}'")
    _ensure_column(conn, "sources", "ingest_job_id", "INTEGER")
    _ensure_column(conn, "search_history", "workspace", "TEXT NOT NULL DEFAULT 'default'")
    _ensure_column(conn, "api_usage", "workspace", "TEXT NOT NULL DEFAULT 'default'")
    _ensure_column(conn, "ingest_jobs", "progress_current", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "ingest_jobs", "progress_total", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "ingest_jobs", "progress_message", "TEXT")
    _ensure_column(conn, "ingest_jobs", "worker_id", "TEXT")
    _ensure_column(conn, "ingest_jobs", "heartbeat_at", "TEXT")
    _ensure_column(conn, "ingest_jobs", "lease_expires_at", "TEXT")
    _ensure_column(conn, "ingest_jobs", "attempt_count", "INTEGER NOT NULL DEFAULT 0")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_sources_ingest_job ON sources(ingest_job_id) "
        "WHERE ingest_job_id IS NOT NULL"
    )
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

def log_source(
    title: str,
    source_type: str,
    url: str | None,
    chunk_count: int,
    tags: list[str] | None = None,
    workspace: str = "default",
    embedding_model: str = DEFAULT_EMBED_MODEL,
    ingest_job_id: int | None = None,
) -> int:
    """Record a newly ingested source. Returns the source id."""
    conn = _get_conn()
    cur = conn.execute(
        """INSERT INTO sources
           (title, source_type, url, chunk_count, tags, workspace, embedding_model, ingest_job_id, ingested_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            title,
            source_type,
            url,
            chunk_count,
            json.dumps(tags or []),
            workspace,
            embedding_model,
            ingest_job_id,
            _utcnow(),
        ),
    )
    conn.commit()
    source_id = cur.lastrowid
    conn.close()
    return source_id


def get_all_sources(workspace: str | None = None) -> list[dict]:
    """Return all ingested sources, most recent first. Optionally filter by workspace."""
    conn = _get_conn()
    if workspace:
        rows = conn.execute(
            "SELECT * FROM sources WHERE workspace = ? ORDER BY ingested_at DESC", (workspace,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM sources ORDER BY ingested_at DESC").fetchall()
    conn.close()
    return [_source_from_row(r) for r in rows]


def get_source(source_id: int) -> dict | None:
    """Return a single source by id, or None if it does not exist."""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
    conn.close()
    return _source_from_row(row)


def get_source_by_ingest_job(ingest_job_id: int) -> dict | None:
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM sources WHERE ingest_job_id = ?",
        (ingest_job_id,),
    ).fetchone()
    conn.close()
    return _source_from_row(row)


def get_all_tags(workspace: str | None = None) -> list[str]:
    """Return a sorted list of every unique tag in use."""
    conn = _get_conn()
    if workspace:
        rows = conn.execute("SELECT tags FROM sources WHERE workspace = ?", (workspace,)).fetchall()
    else:
        rows = conn.execute("SELECT tags FROM sources").fetchall()
    conn.close()
    tags: set[str] = set()
    for r in rows:
        tags.update(json.loads(r["tags"] or "[]"))
    return sorted(tags)


def get_workspaces() -> list[str]:
    """Return a sorted list of all workspaces that have at least one source."""
    conn = _get_conn()
    rows = conn.execute("SELECT DISTINCT workspace FROM sources ORDER BY workspace").fetchall()
    conn.close()
    return [r["workspace"] for r in rows]


def get_embedding_models(workspace: str | None = None) -> list[str]:
    """Return distinct embedding models used by stored sources."""
    conn = _get_conn()
    if workspace:
        rows = conn.execute(
            "SELECT DISTINCT embedding_model FROM sources WHERE workspace = ? ORDER BY embedding_model",
            (workspace,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT DISTINCT embedding_model FROM sources ORDER BY embedding_model"
        ).fetchall()
    conn.close()
    return [r["embedding_model"] or DEFAULT_EMBED_MODEL for r in rows]


def update_source_tags(source_id: int, tags: list[str]) -> None:
    conn = _get_conn()
    conn.execute("UPDATE sources SET tags = ? WHERE id = ?", (json.dumps(tags), source_id))
    conn.commit()
    conn.close()


def update_source_embedding_model(source_id: int, embedding_model: str) -> None:
    conn = _get_conn()
    conn.execute("UPDATE sources SET embedding_model = ? WHERE id = ?", (embedding_model, source_id))
    conn.commit()
    conn.close()


def delete_source(source_id: int) -> None:
    """Delete a source record and all its chunks."""
    conn = _get_conn()
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("DELETE FROM chunks WHERE source_id = ?", (source_id,))
    conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Chunks
# ---------------------------------------------------------------------------

def log_chunks(source_id: int, chroma_ids: list[str], texts: list[str]) -> None:
    """Store chunk text and chroma IDs for a source."""
    conn = _get_conn()
    conn.executemany(
        "INSERT INTO chunks (source_id, chroma_id, chunk_index, text) VALUES (?, ?, ?, ?)",
        [(source_id, cid, i, text) for i, (cid, text) in enumerate(zip(chroma_ids, texts))],
    )
    conn.commit()
    conn.close()


def get_chunks_for_source(source_id: int) -> list[dict]:
    """Return all chunks for a source, in order."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM chunks WHERE source_id = ? ORDER BY chunk_index",
        (source_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_chunk_preview_for_source(source_id: int) -> str:
    """Return the first chunk text for a source, or an empty string."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT text FROM chunks WHERE source_id = ? ORDER BY chunk_index LIMIT 1",
        (source_id,),
    ).fetchone()
    conn.close()
    return row["text"] if row else ""


def get_chunk(chunk_id: int) -> dict | None:
    """Return a single chunk row by id."""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM chunks WHERE id = ?", (chunk_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_chroma_ids_for_source(source_id: int) -> list[str]:
    """Return all ChromaDB IDs for chunks belonging to a source."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT chroma_id FROM chunks WHERE source_id = ?", (source_id,)
    ).fetchall()
    conn.close()
    return [r["chroma_id"] for r in rows]


def update_chunk_text(chunk_id: int, new_text: str) -> None:
    """Update the text of a single chunk in SQLite."""
    conn = _get_conn()
    conn.execute("UPDATE chunks SET text = ? WHERE id = ?", (new_text, chunk_id))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Search history
# ---------------------------------------------------------------------------

def log_search(
    question: str,
    answer: str,
    sources: list[dict],
    tags_used: list[str],
    workspace: str = "default",
) -> None:
    """Record a search query and its answer."""
    conn = _get_conn()
    conn.execute(
        """INSERT INTO search_history (question, answer, sources, tags_used, workspace, searched_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (question, answer, json.dumps(sources), json.dumps(tags_used), workspace,
         _utcnow()),
    )
    conn.commit()
    conn.close()


def get_search_history(limit: int = 50, workspace: str | None = None) -> list[dict]:
    """Return recent search history, newest first."""
    conn = _get_conn()
    if workspace:
        rows = conn.execute(
            "SELECT * FROM search_history WHERE workspace = ? ORDER BY searched_at DESC LIMIT ?",
            (workspace, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM search_history ORDER BY searched_at DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["sources"] = json.loads(d.get("sources") or "[]")
        d["tags_used"] = json.loads(d.get("tags_used") or "[]")
        result.append(d)
    return result


def delete_search_history(workspace: str | None = None) -> int:
    """Delete all search history. Returns count of deleted rows."""
    conn = _get_conn()
    if workspace:
        cur = conn.execute("DELETE FROM search_history WHERE workspace = ?", (workspace,))
    else:
        cur = conn.execute("DELETE FROM search_history")
    conn.commit()
    count = cur.rowcount
    conn.close()
    return count


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

def get_stats(workspace: str | None = None) -> dict:
    """Return aggregate stats about the knowledge base."""
    conn = _get_conn()
    ws_filter = " WHERE workspace = ?" if workspace else ""
    ws_params = (workspace,) if workspace else ()

    source_count = conn.execute(f"SELECT COUNT(*) as c FROM sources{ws_filter}", ws_params).fetchone()["c"]

    if workspace:
        chunk_count = conn.execute(
            "SELECT COUNT(*) as c FROM chunks WHERE source_id IN (SELECT id FROM sources WHERE workspace = ?)",
            (workspace,),
        ).fetchone()["c"]
    else:
        chunk_count = conn.execute("SELECT COUNT(*) as c FROM chunks").fetchone()["c"]

    if workspace:
        query_count = conn.execute(
            "SELECT COUNT(*) as c FROM search_history WHERE workspace = ?",
            (workspace,),
        ).fetchone()["c"]
    else:
        query_count = conn.execute("SELECT COUNT(*) as c FROM search_history").fetchone()["c"]

    type_counts = conn.execute(
        f"SELECT source_type, COUNT(*) as c FROM sources{ws_filter} GROUP BY source_type ORDER BY c DESC",
        ws_params,
    ).fetchall()

    tag_counts = conn.execute(f"SELECT tags FROM sources{ws_filter}", ws_params).fetchall()
    conn.close()

    tag_freq: dict[str, int] = {}
    for r in tag_counts:
        for tag in json.loads(r["tags"] or "[]"):
            tag_freq[tag] = tag_freq.get(tag, 0) + 1

    return {
        "source_count": source_count,
        "chunk_count": chunk_count,
        "query_count": query_count,
        "type_breakdown": {r["source_type"]: r["c"] for r in type_counts},
        "tag_frequency": dict(sorted(tag_freq.items(), key=lambda x: x[1], reverse=True)),
    }


# ---------------------------------------------------------------------------
# API usage tracking
# ---------------------------------------------------------------------------

def log_api_usage(model_id: str, operation: str, input_tokens: int,
                  output_tokens: int, cost_usd: float, workspace: str = "default") -> None:
    conn = _get_conn()
    conn.execute(
        """INSERT INTO api_usage (model_id, operation, input_tokens, output_tokens, cost_usd, workspace, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (model_id, operation, input_tokens, output_tokens, cost_usd, workspace,
         _utcnow()),
    )
    conn.commit()
    conn.close()


def get_api_usage_stats(workspace: str | None = None) -> dict:
    """Return aggregate API usage stats."""
    conn = _get_conn()
    where_clause = " WHERE workspace = ?" if workspace else ""
    params = (workspace,) if workspace else ()
    total = conn.execute(
        "SELECT COALESCE(SUM(input_tokens),0) as inp, COALESCE(SUM(output_tokens),0) as out, "
        f"COALESCE(SUM(cost_usd),0) as cost, COUNT(*) as calls FROM api_usage{where_clause}",
        params,
    ).fetchone()
    by_model = conn.execute(
        "SELECT model_id, COUNT(*) as calls, SUM(input_tokens) as inp, "
        "SUM(output_tokens) as out, SUM(cost_usd) as cost "
        f"FROM api_usage{where_clause} GROUP BY model_id ORDER BY cost DESC",
        params,
    ).fetchall()
    by_operation = conn.execute(
        "SELECT operation, COUNT(*) as calls, SUM(cost_usd) as cost "
        f"FROM api_usage{where_clause} GROUP BY operation ORDER BY cost DESC",
        params,
    ).fetchall()
    recent = conn.execute(
        f"SELECT * FROM api_usage{where_clause} ORDER BY created_at DESC LIMIT 20",
        params,
    ).fetchall()
    conn.close()
    return {
        "total_input_tokens": total["inp"],
        "total_output_tokens": total["out"],
        "total_cost_usd": round(total["cost"], 6),
        "total_calls": total["calls"],
        "by_model": [dict(r) for r in by_model],
        "by_operation": [dict(r) for r in by_operation],
        "recent": [dict(r) for r in recent],
    }


# ---------------------------------------------------------------------------
# Background ingest jobs
# ---------------------------------------------------------------------------

def create_ingest_job(
    job_type: str,
    title: str,
    payload: dict,
    workspace: str = "default",
    progress_total: int = 0,
    progress_message: str | None = None,
) -> int:
    conn = _get_conn()
    cur = conn.execute(
        """INSERT INTO ingest_jobs
           (job_type, title, workspace, payload, status, progress_total, progress_message, created_at)
           VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)""",
        (
            job_type,
            title,
            workspace,
            json.dumps(payload),
            progress_total,
            progress_message,
            _utcnow(),
        ),
    )
    conn.commit()
    job_id = cur.lastrowid
    conn.close()
    return job_id


def get_ingest_job(job_id: int) -> dict | None:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM ingest_jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    return _job_from_row(row)


def get_ingest_jobs(limit: int = 25, workspace: str | None = None) -> list[dict]:
    conn = _get_conn()
    if workspace:
        rows = conn.execute(
            "SELECT * FROM ingest_jobs WHERE workspace = ? ORDER BY created_at DESC LIMIT ?",
            (workspace, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM ingest_jobs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()
    return [_job_from_row(row) for row in rows]


def claim_next_ingest_job(worker_id: str, lease_seconds: int) -> dict | None:
    conn = _get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        now = _utcnow()
        conn.execute(
            """UPDATE ingest_jobs
               SET status = 'pending', worker_id = NULL, heartbeat_at = NULL, lease_expires_at = NULL,
                   progress_current = 0,
                   progress_message = COALESCE(progress_message, 'Recovered after stale worker lease')
               WHERE status = 'running' AND lease_expires_at IS NULL"""
        )
        row = conn.execute(
            """SELECT * FROM ingest_jobs
               WHERE status = 'pending'
                  OR (status = 'running' AND lease_expires_at < ?)
               ORDER BY CASE WHEN status = 'pending' THEN 0 ELSE 1 END, created_at ASC
               LIMIT 1""",
            (now,),
        ).fetchone()
        if row is None:
            conn.commit()
            return None

        lease_expires_at = datetime.fromisoformat(now).timestamp() + lease_seconds
        lease_iso = datetime.fromtimestamp(lease_expires_at, tz=timezone.utc).isoformat()
        cur = conn.execute(
            """UPDATE ingest_jobs
               SET status = 'running',
                   started_at = COALESCE(started_at, ?),
                   worker_id = ?,
                   heartbeat_at = ?,
                   lease_expires_at = ?,
                   finished_at = NULL,
                   error = NULL,
                   attempt_count = attempt_count + 1,
                   progress_current = CASE
                       WHEN status = 'pending' THEN progress_current
                       ELSE 0
                   END
               WHERE id = ?
                 AND (
                   status = 'pending'
                   OR (status = 'running' AND lease_expires_at < ?)
                 )""",
            (now, worker_id, now, lease_iso, row["id"], now),
        )
        if cur.rowcount != 1:
            conn.rollback()
            return None
        conn.commit()
        job = _job_from_row(row)
        job["status"] = "running"
        job["started_at"] = row["started_at"] or now
        job["worker_id"] = worker_id
        job["heartbeat_at"] = now
        job["lease_expires_at"] = lease_iso
        job["attempt_count"] = int(job.get("attempt_count", 0) or 0) + 1
        if row["status"] == "running":
            job["progress_current"] = 0
        return job
    finally:
        conn.close()


def update_ingest_job_progress(
    job_id: int,
    worker_id: str,
    progress_current: int,
    *,
    progress_total: int | None = None,
    progress_message: str | None = None,
    lease_seconds: int = 0,
) -> bool:
    conn = _get_conn()
    now = _utcnow()
    params: list[object] = [progress_current]
    assignments = ["progress_current = ?"]
    if progress_total is not None:
        assignments.append("progress_total = ?")
        params.append(progress_total)
    if progress_message is not None:
        assignments.append("progress_message = ?")
        params.append(progress_message)
    assignments.append("heartbeat_at = ?")
    params.append(now)
    if lease_seconds > 0:
        lease_expires_at = datetime.fromtimestamp(
            datetime.fromisoformat(now).timestamp() + lease_seconds,
            tz=timezone.utc,
        ).isoformat()
        assignments.append("lease_expires_at = ?")
        params.append(lease_expires_at)
    params.extend([job_id, worker_id])
    cur = conn.execute(
        f"UPDATE ingest_jobs SET {', '.join(assignments)} WHERE id = ? AND worker_id = ? AND status = 'running'",
        params,
    )
    conn.commit()
    updated = cur.rowcount == 1
    conn.close()
    return updated


def touch_ingest_job_lease(job_id: int, worker_id: str, lease_seconds: int) -> bool:
    conn = _get_conn()
    now = _utcnow()
    lease_expires_at = datetime.fromtimestamp(
        datetime.fromisoformat(now).timestamp() + lease_seconds,
        tz=timezone.utc,
    ).isoformat()
    cur = conn.execute(
        """UPDATE ingest_jobs
           SET heartbeat_at = ?, lease_expires_at = ?
           WHERE id = ? AND worker_id = ? AND status = 'running'""",
        (now, lease_expires_at, job_id, worker_id),
    )
    conn.commit()
    updated = cur.rowcount == 1
    conn.close()
    return updated


def complete_ingest_job(job_id: int, result: dict) -> None:
    conn = _get_conn()
    conn.execute(
        """UPDATE ingest_jobs
           SET status = 'succeeded',
               result = ?,
               error = NULL,
               finished_at = ?,
               heartbeat_at = NULL,
               lease_expires_at = NULL,
               progress_current = CASE
                   WHEN progress_total > 0 THEN progress_total
                   ELSE progress_current
               END
           WHERE id = ?""",
        (json.dumps(result), _utcnow(), job_id),
    )
    conn.commit()
    conn.close()


def fail_ingest_job(job_id: int, error: str) -> None:
    conn = _get_conn()
    conn.execute(
        """UPDATE ingest_jobs
           SET status = 'failed',
               error = ?,
               finished_at = ?,
               heartbeat_at = NULL,
               lease_expires_at = NULL
           WHERE id = ?""",
        (error, _utcnow(), job_id),
    )
    conn.commit()
    conn.close()


def cancel_ingest_job(job_id: int) -> str | None:
    conn = _get_conn()
    cur = conn.execute(
        """UPDATE ingest_jobs
           SET status = 'cancelled', finished_at = ?
           WHERE id = ? AND status = 'pending'""",
        (_utcnow(), job_id),
    )
    if cur.rowcount == 1:
        conn.commit()
        conn.close()
        return "cancelled"

    cur = conn.execute(
        """UPDATE ingest_jobs
           SET status = 'cancelling'
           WHERE id = ? AND status = 'running'""",
        (job_id,),
    )
    conn.commit()
    conn.close()
    if cur.rowcount == 1:
        return "cancelling"
    return None


def is_ingest_job_cancelling(job_id: int, worker_id: str) -> bool:
    conn = _get_conn()
    row = conn.execute(
        "SELECT 1 FROM ingest_jobs WHERE id = ? AND worker_id = ? AND status = 'cancelling'",
        (job_id, worker_id),
    ).fetchone()
    conn.close()
    return row is not None


def mark_ingest_job_cancelled(job_id: int, worker_id: str | None = None) -> None:
    conn = _get_conn()
    if worker_id:
        conn.execute(
            """UPDATE ingest_jobs
               SET status = 'cancelled',
                   finished_at = ?,
                   heartbeat_at = NULL,
                   lease_expires_at = NULL
               WHERE id = ? AND worker_id = ?""",
            (_utcnow(), job_id, worker_id),
        )
    else:
        conn.execute(
            """UPDATE ingest_jobs
               SET status = 'cancelled',
                   finished_at = ?,
                   heartbeat_at = NULL,
                   lease_expires_at = NULL
               WHERE id = ?""",
            (_utcnow(), job_id),
        )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# RSS feeds
# ---------------------------------------------------------------------------

def add_rss_feed(url: str, title: str | None = None, tags: list[str] | None = None,
                 workspace: str = "default") -> int:
    conn = _get_conn()
    cur = conn.execute(
        """INSERT OR IGNORE INTO rss_feeds (url, title, tags, workspace, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (url, title, json.dumps(tags or []), workspace,
         datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    feed_id = cur.lastrowid
    conn.close()
    return feed_id


def get_rss_feeds(workspace: str | None = None) -> list[dict]:
    conn = _get_conn()
    if workspace:
        rows = conn.execute(
            "SELECT * FROM rss_feeds WHERE workspace = ? ORDER BY created_at DESC", (workspace,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM rss_feeds ORDER BY created_at DESC").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["tags"] = json.loads(d.get("tags") or "[]")
        result.append(d)
    return result


def update_rss_feed_fetched(feed_id: int, last_entry_id: str | None = None) -> None:
    conn = _get_conn()
    conn.execute(
        "UPDATE rss_feeds SET last_fetched = ?, last_entry_id = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(), last_entry_id, feed_id),
    )
    conn.commit()
    conn.close()


def delete_rss_feed(feed_id: int) -> None:
    conn = _get_conn()
    conn.execute("DELETE FROM rss_feeds WHERE id = ?", (feed_id,))
    conn.commit()
    conn.close()


def toggle_rss_feed(feed_id: int, active: bool) -> None:
    conn = _get_conn()
    conn.execute("UPDATE rss_feeds SET active = ? WHERE id = ?", (1 if active else 0, feed_id))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Evaluation pairs
# ---------------------------------------------------------------------------

def add_eval_pair(question: str, expected_answer: str, tags: list[str] | None = None,
                  workspace: str = "default") -> int:
    conn = _get_conn()
    cur = conn.execute(
        """INSERT INTO eval_pairs (question, expected_answer, tags, workspace, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (question, expected_answer, json.dumps(tags or []), workspace,
         datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    pair_id = cur.lastrowid
    conn.close()
    return pair_id


def get_eval_pairs(workspace: str | None = None) -> list[dict]:
    conn = _get_conn()
    if workspace:
        rows = conn.execute(
            "SELECT * FROM eval_pairs WHERE workspace = ? ORDER BY created_at DESC", (workspace,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM eval_pairs ORDER BY created_at DESC").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["tags"] = json.loads(d.get("tags") or "[]")
        result.append(d)
    return result


def delete_eval_pair(pair_id: int) -> None:
    conn = _get_conn()
    conn.execute("DELETE FROM eval_pairs WHERE id = ?", (pair_id,))
    conn.commit()
    conn.close()
