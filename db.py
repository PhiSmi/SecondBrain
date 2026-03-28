"""SQLite metadata helpers for tracking ingested sources."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "metadata.db"


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            source_type TEXT NOT NULL,  -- 'text' or 'url'
            url TEXT,
            chunk_count INTEGER NOT NULL,
            ingested_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def log_source(title: str, source_type: str, url: str | None, chunk_count: int) -> int:
    """Record a newly ingested source. Returns the source id."""
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO sources (title, source_type, url, chunk_count, ingested_at) VALUES (?, ?, ?, ?, ?)",
        (title, source_type, url, chunk_count, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    source_id = cur.lastrowid
    conn.close()
    return source_id


def get_all_sources() -> list[dict]:
    """Return all ingested sources, most recent first."""
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM sources ORDER BY ingested_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_source(source_id: int) -> None:
    """Delete a source record by id."""
    conn = _get_conn()
    conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))
    conn.commit()
    conn.close()
