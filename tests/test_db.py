"""Tests for SQLite database layer."""

import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
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

    def test_get_single_source(self):
        sid = db.log_source("A", "text", None, 1, embedding_model="model-a")
        src = db.get_source(sid)
        assert src["title"] == "A"
        assert src["embedding_model"] == "model-a"

    def test_get_embedding_models(self):
        db.log_source("A", "text", None, 1, workspace="alpha", embedding_model="model-a")
        db.log_source("B", "text", None, 1, workspace="alpha", embedding_model="model-b")
        assert db.get_embedding_models("alpha") == ["model-a", "model-b"]


class TestWorkspaces:
    def setup_method(self):
        self._orig = db.DB_PATH
        db.DB_PATH = Path(_temp_db())

    def teardown_method(self):
        os.unlink(db.DB_PATH)
        db.DB_PATH = self._orig

    def test_create_workspace_persists_without_sources(self):
        created = db.create_workspace("Project Alpha")
        assert created == "project-alpha"
        assert "project-alpha" in db.get_workspaces()

    def test_create_workspace_requires_real_name(self):
        try:
            db.create_workspace("   ")
        except ValueError as exc:
            assert "Workspace name" in str(exc)
        else:
            raise AssertionError("Expected ValueError for blank workspace name")

    def test_workspace_is_registered_from_activity(self):
        db.log_search("Q", "A", [], [], workspace="new-space")
        assert "new-space" in db.get_workspaces()


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

    def test_get_single_chunk(self):
        sid = db.log_source("Test", "text", None, 1)
        db.log_chunks(sid, ["c1"], ["original"])
        chunks = db.get_chunks_for_source(sid)
        chunk = db.get_chunk(chunks[0]["id"])
        assert chunk["chroma_id"] == "c1"

    def test_get_chunk_preview(self):
        sid = db.log_source("Test", "text", None, 2)
        db.log_chunks(sid, ["c1", "c2"], ["first chunk", "second chunk"])
        assert db.get_chunk_preview_for_source(sid) == "first chunk"


class TestSearchHistory:
    def setup_method(self):
        self._orig = db.DB_PATH
        db.DB_PATH = Path(_temp_db())

    def teardown_method(self):
        os.unlink(db.DB_PATH)
        db.DB_PATH = self._orig

    def test_log_and_get_history(self):
        db.log_search("What is RAG?", "RAG stands for...", [{"title": "T"}], ["ml"], workspace="work")
        history = db.get_search_history()
        assert len(history) == 1
        assert history[0]["question"] == "What is RAG?"
        assert history[0]["tags_used"] == ["ml"]
        assert history[0]["workspace"] == "work"

    def test_history_workspace_filter(self):
        db.log_search("Q1", "A1", [], [], workspace="work")
        db.log_search("Q2", "A2", [], [], workspace="personal")
        history = db.get_search_history(workspace="work")
        assert len(history) == 1
        assert history[0]["question"] == "Q1"

    def test_delete_history(self):
        db.log_search("Q1", "A1", [], [], workspace="work")
        db.log_search("Q2", "A2", [], [], workspace="personal")
        count = db.delete_search_history(workspace="work")
        assert count == 1
        assert len(db.get_search_history()) == 1


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
        db.log_search("test?", "answer", [], [], workspace="default")
        stats = db.get_stats()
        assert stats["source_count"] == 1
        assert stats["chunk_count"] == 3
        assert stats["query_count"] == 1
        assert stats["type_breakdown"]["url"] == 1
        assert stats["tag_frequency"]["web"] == 1


class TestApiUsage:
    def setup_method(self):
        self._orig = db.DB_PATH
        db.DB_PATH = Path(_temp_db())

    def teardown_method(self):
        os.unlink(db.DB_PATH)
        db.DB_PATH = self._orig

    def test_usage_workspace_filter(self):
        db.log_api_usage("model-a", "query", 100, 50, 0.01, workspace="work")
        db.log_api_usage("model-b", "query", 100, 50, 0.02, workspace="personal")
        usage = db.get_api_usage_stats(workspace="work")
        assert usage["total_calls"] == 1
        assert usage["by_model"][0]["model_id"] == "model-a"


class TestIngestJobs:
    def setup_method(self):
        self._orig = db.DB_PATH
        db.DB_PATH = Path(_temp_db())

    def teardown_method(self):
        os.unlink(db.DB_PATH)
        db.DB_PATH = self._orig

    def test_job_lifecycle(self):
        job_id = db.create_ingest_job(
            "text",
            title="Queued note",
            payload={"text": "hello world"},
            workspace="work",
            progress_total=4,
            progress_message="Queued",
        )
        jobs = db.get_ingest_jobs(workspace="work")
        assert len(jobs) == 1
        assert jobs[0]["status"] == "pending"
        assert jobs[0]["progress_total"] == 4

        claimed = db.claim_next_ingest_job("worker-a", lease_seconds=300)
        assert claimed is not None
        assert claimed["id"] == job_id
        assert claimed["status"] == "running"
        assert claimed["worker_id"] == "worker-a"

        updated = db.update_ingest_job_progress(
            job_id,
            "worker-a",
            2,
            progress_message="Embedding",
            lease_seconds=300,
        )
        assert updated is True
        result_updated = db.update_ingest_job_result(
            job_id,
            "worker-a",
            {"stage": "embedding"},
            lease_seconds=300,
        )
        assert result_updated is True

        db.complete_ingest_job(job_id, {"chunks": 3})
        stored = db.get_ingest_job(job_id)
        assert stored["status"] == "succeeded"
        assert stored["result"]["chunks"] == 3
        assert stored["progress_current"] == 4
        assert stored["progress_message"] == "Completed"

    def test_cancel_pending_job(self):
        job_id = db.create_ingest_job(
            "url",
            title="Queued URL",
            payload={"url": "https://example.com"},
            workspace="research",
        )
        assert db.cancel_ingest_job(job_id) == "cancelled"
        job = db.get_ingest_job(job_id)
        assert job["status"] == "cancelled"
        assert job["progress_message"] == "Cancelled"

    def test_reclaim_stale_running_job(self):
        job_id = db.create_ingest_job(
            "text",
            title="Retry me",
            payload={"text": "hello"},
            workspace="default",
        )
        claimed = db.claim_next_ingest_job("worker-a", lease_seconds=300)
        assert claimed is not None
        conn = db._get_conn()
        stale = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        conn.execute(
            """UPDATE ingest_jobs
               SET lease_expires_at = ?, heartbeat_at = ?, status = 'running'
               WHERE id = ?""",
            (stale, stale, job_id),
        )
        conn.commit()
        conn.close()

        reclaimed = db.claim_next_ingest_job("worker-b", lease_seconds=300)
        assert reclaimed is not None
        assert reclaimed["id"] == job_id
        assert reclaimed["worker_id"] == "worker-b"
        assert reclaimed["attempt_count"] == 2

    def test_cancel_running_job_marks_cancelling(self):
        job_id = db.create_ingest_job(
            "text",
            title="Stop me",
            payload={"text": "hello"},
            workspace="default",
        )
        claimed = db.claim_next_ingest_job("worker-a", lease_seconds=300)
        assert claimed is not None
        assert db.cancel_ingest_job(job_id) == "cancelling"
        assert db.is_ingest_job_cancelling(job_id, "worker-a") is True
        job = db.get_ingest_job(job_id)
        assert job["progress_message"] == "Stopping after the current step"
        db.mark_ingest_job_cancelled(job_id, "worker-a")
        job = db.get_ingest_job(job_id)
        assert job["status"] == "cancelled"
        assert job["progress_message"] == "Cancelled"

    def test_fail_job_sets_terminal_progress_message(self):
        job_id = db.create_ingest_job(
            "text",
            title="Break me",
            payload={"text": "hello"},
            workspace="default",
            progress_total=4,
            progress_message="Queued",
        )
        claimed = db.claim_next_ingest_job("worker-a", lease_seconds=300)
        assert claimed is not None
        db.fail_ingest_job(job_id, "boom")
        job = db.get_ingest_job(job_id)
        assert job["status"] == "failed"
        assert job["progress_message"] == "Failed"

    def test_get_open_jobs_filters_terminal_states(self):
        pending_id = db.create_ingest_job(
            "text",
            title="Pending",
            payload={"text": "hello"},
            workspace="default",
        )
        running_id = db.create_ingest_job(
            "text",
            title="Running",
            payload={"text": "world"},
            workspace="default",
        )
        failed_id = db.create_ingest_job(
            "text",
            title="Failed",
            payload={"text": "!"},
            workspace="default",
        )
        claimed = db.claim_next_ingest_job("worker-a", lease_seconds=300)
        assert claimed is not None
        claimed = db.claim_next_ingest_job("worker-b", lease_seconds=300)
        assert claimed is not None
        db.fail_ingest_job(failed_id, "boom")

        open_jobs = db.get_open_ingest_jobs(workspace="default")
        open_ids = {job["id"] for job in open_jobs}
        assert pending_id in open_ids or running_id in open_ids
        assert failed_id not in open_ids
        assert all(job["status"] in {"pending", "running", "cancelling"} for job in open_jobs)

    def test_delete_ingest_jobs_returns_deleted_rows(self):
        failed_id = db.create_ingest_job(
            "text",
            title="Failed",
            payload={"text": "fail"},
            workspace="work",
        )
        success_id = db.create_ingest_job(
            "text",
            title="Done",
            payload={"text": "done"},
            workspace="work",
        )
        other_workspace_id = db.create_ingest_job(
            "text",
            title="Other",
            payload={"text": "other"},
            workspace="personal",
        )
        db.fail_ingest_job(failed_id, "boom")
        db.complete_ingest_job(success_id, {"chunks": 1})
        db.complete_ingest_job(other_workspace_id, {"chunks": 1})

        deleted = db.delete_ingest_jobs({"failed", "succeeded"}, workspace="work")
        deleted_ids = {job["id"] for job in deleted}
        assert deleted_ids == {failed_id, success_id}
        assert db.get_ingest_job(failed_id) is None
        assert db.get_ingest_job(success_id) is None
        assert db.get_ingest_job(other_workspace_id) is not None
