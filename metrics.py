"""Prometheus metrics middleware and instrumentation for SecondBrain.

Exposes all n7_secondbrain_* metrics and a /metrics endpoint protected by
METRICS_SECRET bearer token.
"""

from __future__ import annotations

import logging
import os
import time

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

_METRICS_SECRET = os.environ.get("METRICS_SECRET", "")

# ---------------------------------------------------------------------------
# HTTP metrics
# ---------------------------------------------------------------------------
REQUEST_COUNT = Counter(
    "n7_secondbrain_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)
REQUEST_DURATION = Histogram(
    "n7_secondbrain_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
IN_PROGRESS = Gauge(
    "n7_secondbrain_http_requests_in_progress",
    "In-flight HTTP requests",
    ["method"],
)

# ---------------------------------------------------------------------------
# Query pipeline metrics
# ---------------------------------------------------------------------------
QUERY_DURATION = Histogram(
    "n7_secondbrain_query_duration_seconds",
    "Query pipeline stage duration",
    ["stage"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 20),
)
QUERY_CHUNKS = Histogram(
    "n7_secondbrain_query_chunks_retrieved",
    "Number of chunks returned per query",
    buckets=(1, 2, 3, 5, 8, 13, 20),
)

# ---------------------------------------------------------------------------
# Ingestion metrics
# ---------------------------------------------------------------------------
INGEST_TOTAL = Counter(
    "n7_secondbrain_ingest_total",
    "Ingestion operations by type and status",
    ["source_type", "status"],
)
INGEST_CHUNKS = Counter(
    "n7_secondbrain_ingest_chunks_total",
    "Total chunks ingested",
)

# ---------------------------------------------------------------------------
# ChromaDB metrics (updated lazily at scrape time)
# ---------------------------------------------------------------------------
CHROMA_COLLECTION_SIZE = Gauge(
    "n7_secondbrain_chroma_collection_size",
    "Documents in ChromaDB collection",
    ["collection"],
)

# ---------------------------------------------------------------------------
# LLM usage metrics
# ---------------------------------------------------------------------------
LLM_TOKENS = Counter(
    "n7_secondbrain_llm_tokens_total",
    "LLM token consumption",
    ["model", "direction"],
)


def _normalize_endpoint(path: str) -> str:
    """Collapse request path to first 2 segments to bound cardinality."""
    parts = path.strip("/").split("/")
    if not parts or parts == [""]:
        return "/"
    if len(parts) <= 2:
        return "/" + "/".join(parts)
    return "/" + "/".join(parts[:2])


class MetricsMiddleware(BaseHTTPMiddleware):
    """Records HTTP request count, latency, and in-flight gauge."""

    async def dispatch(self, request: Request, call_next) -> Response:  # noqa: ANN001
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        endpoint = _normalize_endpoint(request.url.path)
        IN_PROGRESS.labels(method=method).inc()
        start = time.perf_counter()
        status = "500"
        try:
            response = await call_next(request)
            status = str(response.status_code)
            return response
        except Exception:
            raise
        finally:
            duration = time.perf_counter() - start
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status_code=status).inc()
            REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)
            IN_PROGRESS.labels(method=method).dec()


# ---------------------------------------------------------------------------
# Instrumentation helpers (called from query.py and ingest.py)
# ---------------------------------------------------------------------------


def observe_query_stage(stage: str, duration: float) -> None:
    """Record the duration of a query pipeline stage."""
    QUERY_DURATION.labels(stage=stage).observe(duration)


def observe_chunks_retrieved(count: int) -> None:
    """Record how many chunks were retrieved for a query."""
    QUERY_CHUNKS.observe(count)


def record_ingest(source_type: str, status: str, chunk_count: int = 0) -> None:
    """Record an ingestion operation."""
    INGEST_TOTAL.labels(source_type=source_type, status=status).inc()
    if chunk_count > 0:
        INGEST_CHUNKS.inc(chunk_count)


def record_llm_usage(model: str, input_tokens: int, output_tokens: int) -> None:
    """Record LLM token consumption."""
    if input_tokens:
        LLM_TOKENS.labels(model=model, direction="input").inc(input_tokens)
    if output_tokens:
        LLM_TOKENS.labels(model=model, direction="output").inc(output_tokens)


def _update_chroma_gauges() -> None:
    """Update ChromaDB collection size gauges at scrape time."""
    try:
        import chromadb
        client = chromadb.PersistentClient(path="data/chroma")
        for col in client.list_collections():
            CHROMA_COLLECTION_SIZE.labels(collection=col.name).set(col.count())
    except Exception:
        logger.debug("Failed to update ChromaDB gauges", exc_info=True)


def metrics_endpoint(request: Request) -> Response:
    """Return Prometheus metrics, protected by METRICS_SECRET bearer token."""
    if _METRICS_SECRET:
        auth = request.headers.get("authorization", "")
        if auth != f"Bearer {_METRICS_SECRET}":
            return Response("Unauthorized", status_code=403)
    _update_chroma_gauges()
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
