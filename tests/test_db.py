"""Tests for SQLite database layer."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import db


def _temp_db():
    """Point db.DB_PATH at a temp file for isolation."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    return tmp.name


class TestSources:
    def setup_method(self):
        self._orig = db.DB_PATH
        db.DB_PATH = Path(_temp_db())

    def teardown_method(self):
        os.unlink(db.DB_PATH)
        db.DB_PATH = self._orig

    def test_log_and_get_source(self):
        sid = db.log_source("Test", "text", None, 5, tags=["demo"])
        assert sid > 0
        sources = db.get_all_sources()
        assert len(sources) == 1
        assert sources[0]["title"] == "Test"
        assert sources[0]["tags"] == ["demo"]

    def test_workspace_filter(self):
        db.log_source("A", "text", None, 1, workspace="work")
        db.log_source("B", "text", None, 1, workspace="personal")
        all_sources = db.get_all_sources()
        assert len(all_sources) == 2
        work_only = db.get_all_sources(workspace="work")
        assert len(work_only) == 1
        assert work_only[0]["title"] == "A"

    def test_get_all_tags(self):
        db.log_source("A", "text", None, 1, tags=["python", "ml"])
        db.log_source("B", "text", None, 1, tags=["python", "web"])
        tags = db.get_all_tags()
        assert tags == ["ml", "python", "web"]

    def test_update_tags(self):
        sid = db.log_source("A", "text", None, 1, tags=["old"])
        db.update_source_tags(sid, ["new1", "new2"])
        src = db.get_all_sources()[0]
        assert src["tags"] == ["new1", "new2"]

    def test_delete_source(self):
        sid = db.log_source("A", "text", None, 1)
        db.log_chunks(sid, ["chroma_1"], ["chunk text"])
        db.delete_source(sid)
        assert db.get_all_sources() == []
        assert db.get_chunks_for_source(sid) == []

    def test_get_workspaces(self):
        db.log_source("A", "text", None, 1, workspace="alpha")
        db.log_source("B", "text", None, 1, workspace="beta")
        ws = db.get_workspaces()
        assert "alpha" in ws
        assert "beta" in ws


class TestChunks:
    def setup_method(self):
        self._orig = db.DB_PATH
        db.DB_PATH = Path(_temp_db())

    def teardown_method(self):
        os.unlink(db.DB_PATH)
        db.DB_PATH = self._orig

    def test_log_and_get_chunks(self):
        sid = db.log_source("Test", "text", None, 2)
        db.log_chunks(sid, ["c1", "c2"], ["hello", "world"])
        chunks = db.get_chunks_for_source(sid)
        assert len(chunks) == 2
        assert chunks[0]["text"] == "hello"
        assert chunks[1]["text"] == "world"

    def test_get_chroma_ids(self):
        sid = db.log_source("Test", "text", None, 2)
        db.log_chunks(sid, ["id_a", "id_b"], ["text1", "text2"])
        ids = db.get_chroma_ids_for_source(sid)
        assert ids == ["id_a", "id_b"]

    def test_update_chunk_text(self):
        sid = db.log_source("Test", "text", None, 1)
        db.log_chunks(sid, ["c1"], ["original"])
        chunks = db.get_chunks_for_source(sid)
        db.update_chunk_text(chunks[0]["id"], "edited")
        updated = db.get_chunks_for_source(sid)
        assert updated[0]["text"] == "edited"


class TestSearchHistory:
    def setup_method(self):
        self._orig = db.DB_PATH
        db.DB_PATH = Path(_temp_db())

    def teardown_method(self):
        os.unlink(db.DB_PATH)
        db.DB_PATH = self._orig

    def test_log_and_get_history(self):
        db.log_search("What is RAG?", "RAG stands for...", [{"title": "T"}], ["ml"])
        history = db.get_search_history()
        assert len(history) == 1
        assert history[0]["question"] == "What is RAG?"
        assert history[0]["tags_used"] == ["ml"]

    def test_delete_history(self):
        db.log_search("Q1", "A1", [], [])
        db.log_search("Q2", "A2", [], [])
        count = db.delete_search_history()
        assert count == 2
        assert db.get_search_history() == []


class TestStats:
    def setup_method(self):
        self._orig = db.DB_PATH
        db.DB_PATH = Path(_temp_db())

    def teardown_method(self):
        os.unlink(db.DB_PATH)
        db.DB_PATH = self._orig

    def test_empty_stats(self):
        stats = db.get_stats()
        assert stats["source_count"] == 0
        assert stats["chunk_count"] == 0
        assert stats["query_count"] == 0

    def test_stats_with_data(self):
        sid = db.log_source("A", "url", "http://x", 3, tags=["web"])
        db.log_chunks(sid, ["c1", "c2", "c3"], ["a", "b", "c"])
        db.log_search("test?", "answer", [], [])
        stats = db.get_stats()
        assert stats["source_count"] == 1
        assert stats["chunk_count"] == 3
        assert stats["query_count"] == 1
        assert stats["type_breakdown"]["url"] == 1
        assert stats["tag_frequency"]["web"] == 1
