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
            workspace   TEXT    NOT NULL DEFAULT 'default',
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

        CREATE TABLE IF NOT EXISTS api_usage (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id      TEXT    NOT NULL,
            operation     TEXT    NOT NULL,
            input_tokens  INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            cost_usd      REAL    NOT NULL DEFAULT 0.0,
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
        """
    )
    # Add workspace column if missing (migration for existing DBs)
    try:
        conn.execute("SELECT workspace FROM sources LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE sources ADD COLUMN workspace TEXT NOT NULL DEFAULT 'default'")
        conn.commit()
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
) -> int:
    """Record a newly ingested source. Returns the source id."""
    conn = _get_conn()
    cur = conn.execute(
        """INSERT INTO sources (title, source_type, url, chunk_count, tags, workspace, ingested_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            title,
            source_type,
            url,
            chunk_count,
            json.dumps(tags or []),
            workspace,
            datetime.now(timezone.utc).isoformat(),
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
    result = []
    for r in rows:
        d = dict(r)
        d["tags"] = json.loads(d.get("tags") or "[]")
        result.append(d)
    return result


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


def update_source_tags(source_id: int, tags: list[str]) -> None:
    conn = _get_conn()
    conn.execute("UPDATE sources SET tags = ? WHERE id = ?", (json.dumps(tags), source_id))
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
                  output_tokens: int, cost_usd: float) -> None:
    conn = _get_conn()
    conn.execute(
        """INSERT INTO api_usage (model_id, operation, input_tokens, output_tokens, cost_usd, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (model_id, operation, input_tokens, output_tokens, cost_usd,
         datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


def get_api_usage_stats() -> dict:
    """Return aggregate API usage stats."""
    conn = _get_conn()
    total = conn.execute(
        "SELECT COALESCE(SUM(input_tokens),0) as inp, COALESCE(SUM(output_tokens),0) as out, "
        "COALESCE(SUM(cost_usd),0) as cost, COUNT(*) as calls FROM api_usage"
    ).fetchone()
    by_model = conn.execute(
        "SELECT model_id, COUNT(*) as calls, SUM(input_tokens) as inp, "
        "SUM(output_tokens) as out, SUM(cost_usd) as cost "
        "FROM api_usage GROUP BY model_id ORDER BY cost DESC"
    ).fetchall()
    by_operation = conn.execute(
        "SELECT operation, COUNT(*) as calls, SUM(cost_usd) as cost "
        "FROM api_usage GROUP BY operation ORDER BY cost DESC"
    ).fetchall()
    recent = conn.execute(
        "SELECT * FROM api_usage ORDER BY created_at DESC LIMIT 20"
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
