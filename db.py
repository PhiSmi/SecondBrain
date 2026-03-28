"""SQLite metadata helpers for tracking ingested sources."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "metadata.db"


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
            ingested_at TEXT    NOT NULL
        );

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
            searched_at TEXT    NOT NULL
        );
        """
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
) -> int:
    """Record a newly ingested source. Returns the source id."""
    conn = _get_conn()
    cur = conn.execute(
        """INSERT INTO sources (title, source_type, url, chunk_count, tags, ingested_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            title,
            source_type,
            url,
            chunk_count,
            json.dumps(tags or []),
            datetime.now(timezone.utc).isoformat(),
        ),
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
    result = []
    for r in rows:
        d = dict(r)
        d["tags"] = json.loads(d.get("tags") or "[]")
        result.append(d)
    return result


def get_all_tags() -> list[str]:
    """Return a sorted list of every unique tag in use."""
    conn = _get_conn()
    rows = conn.execute("SELECT tags FROM sources").fetchall()
    conn.close()
    tags: set[str] = set()
    for r in rows:
        tags.update(json.loads(r["tags"] or "[]"))
    return sorted(tags)


def update_source_tags(source_id: int, tags: list[str]) -> None:
    conn = _get_conn()
    conn.execute("UPDATE sources SET tags = ? WHERE id = ?", (json.dumps(tags), source_id))
    conn.commit()
    conn.close()


def delete_source(source_id: int) -> None:
    """Delete a source record and all its chunks."""
    conn = _get_conn()
    conn.execute("PRAGMA foreign_keys = ON")
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


def get_chroma_ids_for_source(source_id: int) -> list[str]:
    """Return all ChromaDB IDs for chunks belonging to a source."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT chroma_id FROM chunks WHERE source_id = ?", (source_id,)
    ).fetchall()
    conn.close()
    return [r["chroma_id"] for r in rows]


# ---------------------------------------------------------------------------
# Search history
# ---------------------------------------------------------------------------

def log_search(question: str, answer: str, sources: list[dict], tags_used: list[str]) -> None:
    """Record a search query and its answer."""
    conn = _get_conn()
    conn.execute(
        """INSERT INTO search_history (question, answer, sources, tags_used, searched_at)
           VALUES (?, ?, ?, ?, ?)""",
        (question, answer, json.dumps(sources), json.dumps(tags_used),
         datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


def get_search_history(limit: int = 50) -> list[dict]:
    """Return recent search history, newest first."""
    conn = _get_conn()
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


def delete_search_history() -> int:
    """Delete all search history. Returns count of deleted rows."""
    conn = _get_conn()
    cur = conn.execute("DELETE FROM search_history")
    conn.commit()
    count = cur.rowcount
    conn.close()
    return count


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

def get_stats() -> dict:
    """Return aggregate stats about the knowledge base."""
    conn = _get_conn()
    source_count = conn.execute("SELECT COUNT(*) as c FROM sources").fetchone()["c"]
    chunk_count = conn.execute("SELECT COUNT(*) as c FROM chunks").fetchone()["c"]
    query_count = conn.execute("SELECT COUNT(*) as c FROM search_history").fetchone()["c"]

    type_counts = conn.execute(
        "SELECT source_type, COUNT(*) as c FROM sources GROUP BY source_type ORDER BY c DESC"
    ).fetchall()

    tag_counts = conn.execute("SELECT tags FROM sources").fetchall()
    conn.close()

    # Compute tag frequency
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
