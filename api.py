"""FastAPI wrapper for SecondBrain — programmatic access to the RAG pipeline.

Run with: uvicorn api:app --host 0.0.0.0 --port 8000
"""

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

load_dotenv(Path(__file__).parent / ".env", override=False)

import background_jobs  # noqa: E402
import db  # noqa: E402
import ingest  # noqa: E402
import query  # noqa: E402

app = FastAPI(
    title="SecondBrain API",
    description="Programmatic access to your personal RAG knowledge base",
    version="2.0",
)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class AskRequest(BaseModel):
    question: str
    tags: list[str] | None = None
    hybrid: bool = True
    use_rerank: bool = False
    model_id: str | None = None
    min_similarity: float = 0.0
    workspace: str | None = None


class AskResponse(BaseModel):
    answer: str
    sources: list[dict]


class IngestTextRequest(BaseModel):
    text: str
    title: str
    tags: list[str] | None = None
    workspace: str | None = None
    embed_model_id: str | None = None
    auto_tag: bool = False


class IngestURLRequest(BaseModel):
    url: str
    title: str | None = None
    tags: list[str] | None = None
    workspace: str | None = None
    embed_model_id: str | None = None
    auto_tag: bool = False


class IngestResponse(BaseModel):
    chunks: int


class JobQueuedResponse(BaseModel):
    job_id: int
    status: str


class TagSuggestRequest(BaseModel):
    text: str
    workspace: str | None = None


class TagSuggestResponse(BaseModel):
    tags: list[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/ask", response_model=AskResponse)
def api_ask(req: AskRequest):
    """Ask a question against the knowledge base."""
    result = query.ask(
        req.question,
        tags=req.tags,
        hybrid=req.hybrid,
        use_rerank=req.use_rerank,
        model_id=req.model_id,
        min_similarity=req.min_similarity,
        workspace=req.workspace,
    )
    return AskResponse(answer=result["answer"], sources=result["sources"])


@app.post("/ingest/text", response_model=IngestResponse)
def api_ingest_text(req: IngestTextRequest):
    """Ingest raw text into the knowledge base."""
    n = ingest.ingest_text(
        req.text,
        title=req.title,
        tags=req.tags,
        workspace=req.workspace,
        embed_model_id=req.embed_model_id,
    )
    return IngestResponse(chunks=n)


@app.post("/ingest/url", response_model=IngestResponse)
def api_ingest_url(req: IngestURLRequest):
    """Fetch and ingest a URL."""
    try:
        n, _ = ingest.ingest_url(
            req.url,
            title=req.title,
            tags=req.tags,
            workspace=req.workspace,
            embed_model_id=req.embed_model_id,
        )
        return IngestResponse(chunks=n)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/jobs/ingest/text", response_model=JobQueuedResponse)
def api_queue_ingest_text(req: IngestTextRequest):
    job_id = background_jobs.queue_text_ingest(
        req.text,
        title=req.title,
        tags=req.tags,
        workspace=req.workspace or "default",
        embed_model_id=req.embed_model_id,
        auto_tag=req.auto_tag,
    )
    return JobQueuedResponse(job_id=job_id, status="pending")


@app.post("/jobs/ingest/url", response_model=JobQueuedResponse)
def api_queue_ingest_url(req: IngestURLRequest):
    job_id = background_jobs.queue_url_ingest(
        req.url,
        title=req.title,
        tags=req.tags,
        workspace=req.workspace or "default",
        embed_model_id=req.embed_model_id,
        auto_tag=req.auto_tag,
    )
    return JobQueuedResponse(job_id=job_id, status="pending")


@app.post("/suggest-tags", response_model=TagSuggestResponse)
def api_suggest_tags(req: TagSuggestRequest):
    """Suggest tags for a piece of content using Claude."""
    tags = query.suggest_tags(req.text, workspace=req.workspace or "default")
    return TagSuggestResponse(tags=tags)


@app.get("/sources")
def api_list_sources(workspace: str | None = None):
    """List all ingested sources."""
    return db.get_all_sources(workspace=workspace)


@app.delete("/sources/{source_id}")
def api_delete_source(source_id: int, workspace: str | None = None):
    """Delete a source and all its vectors."""
    ingest.delete_source(source_id, workspace=workspace)
    return {"deleted": True}


@app.get("/stats")
def api_stats(workspace: str | None = None):
    """Get knowledge base statistics."""
    return db.get_stats(workspace=workspace)


@app.get("/usage")
def api_usage(workspace: str | None = None):
    """Get API usage and cost statistics."""
    return db.get_api_usage_stats(workspace=workspace)


@app.get("/jobs")
def api_jobs(workspace: str | None = None, limit: int = 25):
    background_jobs.ensure_worker_running()
    return db.get_ingest_jobs(limit=limit, workspace=workspace)


@app.get("/jobs/{job_id}")
def api_job(job_id: int):
    background_jobs.ensure_worker_running()
    job = db.get_ingest_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/jobs/{job_id}/cancel")
def api_cancel_job(job_id: int):
    cancelled = background_jobs.cancel_job(job_id)
    if not cancelled:
        raise HTTPException(status_code=409, detail="Job could not be cancelled")
    return {"cancelled": True}


@app.get("/health")
def api_health():
    return {"status": "ok"}
