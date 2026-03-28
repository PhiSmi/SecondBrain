"""FastAPI wrapper for SecondBrain — programmatic access to the RAG pipeline.

Run with: uvicorn api:app --host 0.0.0.0 --port 8000
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

load_dotenv(Path(__file__).parent / ".env", override=False)

import db
import ingest
import query

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


class IngestURLRequest(BaseModel):
    url: str
    title: str | None = None
    tags: list[str] | None = None
    workspace: str | None = None


class IngestResponse(BaseModel):
    chunks: int


class TagSuggestRequest(BaseModel):
    text: str


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
    n = ingest.ingest_text(req.text, title=req.title, tags=req.tags, workspace=req.workspace)
    return IngestResponse(chunks=n)


@app.post("/ingest/url", response_model=IngestResponse)
def api_ingest_url(req: IngestURLRequest):
    """Fetch and ingest a URL."""
    try:
        n, _ = ingest.ingest_url(req.url, title=req.title, tags=req.tags, workspace=req.workspace)
        return IngestResponse(chunks=n)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/suggest-tags", response_model=TagSuggestResponse)
def api_suggest_tags(req: TagSuggestRequest):
    """Suggest tags for a piece of content using Claude."""
    tags = query.suggest_tags(req.text)
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
def api_usage():
    """Get API usage and cost statistics."""
    return db.get_api_usage_stats()


@app.get("/health")
def api_health():
    return {"status": "ok"}
