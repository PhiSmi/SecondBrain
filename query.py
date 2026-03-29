"""Retrieval + Claude answer generation pipeline.

Supports:
- Semantic search (dense embeddings via sentence-transformers)
- Hybrid search (semantic + BM25 keyword, merged via Reciprocal Rank Fusion)
- Tag-scoped retrieval
- Cross-encoder reranking
- Multi-turn conversation history
- Source summarisation
- Streaming responses
- Configurable similarity threshold
"""

import math
import os
import re
from collections import defaultdict
from pathlib import Path

import anthropic
import chromadb
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

import config

load_dotenv(Path(__file__).parent / ".env", override=False)

_cfg = config.retrieval()
CHROMA_PATH = Path(__file__).parent / "data" / "chroma"
COLLECTION_NAME = "secondbrain"
TOP_K = _cfg.get("top_k", 10)
FINAL_K = _cfg.get("final_k", 5)
RRF_K = _cfg.get("rrf_k", 60)

_embed_models: dict[str, SentenceTransformer] = {}
_rerank_model = None  # CrossEncoder, lazy-loaded
_collections: dict[str, chromadb.Collection] = {}
_client: anthropic.Anthropic | None = None

SYSTEM_PROMPT = """You are a helpful research assistant with access to the user's personal knowledge base. Follow these rules:

1. Answer using ONLY the provided context chunks — never your general training knowledge.
2. Cite sources in square brackets after each claim, e.g. [Source Title].
3. If multiple sources cover the same point, synthesise them and cite all.
4. If the context doesn't contain enough to answer, say so clearly and suggest what content to ingest.
5. Be concise. Use bullet points for multi-part answers."""

SUMMARY_PROMPT = """You are a research assistant. Summarise the following text from the user's knowledge base.
Produce exactly 5–7 bullet points. Each bullet should capture a distinct key idea.
Be concise — each bullet should be one sentence. Do not add any preamble or closing remarks."""


def _get_embed_model(model_id: str | None = None) -> SentenceTransformer:
    model_id = model_id or "all-MiniLM-L6-v2"
    if model_id not in _embed_models:
        _embed_models[model_id] = SentenceTransformer(model_id)
    return _embed_models[model_id]


def _get_rerank_model():
    """Lazy-load the cross-encoder reranking model (only when reranking is used)."""
    global _rerank_model
    if _rerank_model is None:
        from sentence_transformers import CrossEncoder
        _rerank_model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _rerank_model


def _collection_name(workspace: str | None = None) -> str:
    ws = workspace or config.workspaces().get("default", "default")
    return f"secondbrain_{ws}" if ws != "default" else COLLECTION_NAME


def _get_collection(workspace: str | None = None) -> chromadb.Collection:
    name = _collection_name(workspace)
    if name not in _collections:
        client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        _collections[name] = client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )
    return _collections[name]


def _get_anthropic() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


# ---------------------------------------------------------------------------
# BM25 (keyword search)
# ---------------------------------------------------------------------------

def _tokenise(text: str) -> list[str]:
    return re.findall(r"\b\w+\b", text.lower())


def _bm25_scores(query: str, documents: list[str], k1: float = 1.5, b: float = 0.75) -> list[float]:
    """Return BM25 relevance scores for each document."""
    if not documents:
        return []

    tokenised_docs = [_tokenise(d) for d in documents]
    avg_dl = sum(len(d) for d in tokenised_docs) / len(tokenised_docs)
    query_terms = _tokenise(query)

    idf: dict[str, float] = {}
    N = len(documents)
    for term in set(query_terms):
        df = sum(1 for d in tokenised_docs if term in d)
        idf[term] = math.log((N - df + 0.5) / (df + 0.5) + 1)

    scores = []
    for doc_tokens in tokenised_docs:
        dl = len(doc_tokens)
        freq: dict[str, int] = defaultdict(int)
        for t in doc_tokens:
            freq[t] += 1
        score = 0.0
        for term in query_terms:
            tf = freq.get(term, 0)
            score += idf.get(term, 0) * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / avg_dl))
        scores.append(score)

    return scores


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion
# ---------------------------------------------------------------------------

def _rrf_merge(ranked_lists: list[list[str]], k: int = RRF_K) -> list[str]:
    """Merge multiple ranked ID lists into one via Reciprocal Rank Fusion."""
    scores: dict[str, float] = defaultdict(float)
    for ranked in ranked_lists:
        for rank, doc_id in enumerate(ranked, 1):
            scores[doc_id] += 1.0 / (k + rank)
    return sorted(scores, key=lambda x: scores[x], reverse=True)


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def retrieve(
    question: str,
    top_k: int = TOP_K,
    tags: list[str] | None = None,
    hybrid: bool = True,
    min_similarity: float = 0.0,
    workspace: str | None = None,
    embed_model_id: str | None = None,
) -> list[dict]:
    """Retrieve the top-k most relevant chunks.

    Args:
        question: The user's question.
        top_k: Number of candidates to retrieve before reranking.
        tags: If provided, only return chunks from sources with these tags.
        hybrid: If True, merge semantic + BM25 results via RRF.
        min_similarity: Filter out chunks below this cosine similarity score.
        workspace: Which workspace collection to search.
        embed_model_id: Which embedding model to use for the query.

    Returns:
        List of chunk dicts with keys: id, text, metadata, semantic_score.
    """
    model = _get_embed_model(embed_model_id)
    collection = _get_collection(workspace)

    total = collection.count()
    if total == 0:
        return []

    n = min(top_k, total)

    where: dict | None = None
    if tags:
        where = {"$or": [{"tags": {"$contains": tag}} for tag in tags]} if len(tags) > 1 else {"tags": {"$contains": tags[0]}}

    query_vec = model.encode([question], show_progress_bar=False).tolist()
    sem_results = collection.query(
        query_embeddings=query_vec,
        n_results=n,
        include=["documents", "metadatas", "distances"],
        where=where,
    )

    sem_docs = sem_results["documents"][0]
    sem_metas = sem_results["metadatas"][0]
    sem_dists = sem_results["distances"][0]
    sem_ids = sem_results["ids"][0]

    chunk_map: dict[str, dict] = {}
    for doc, meta, dist, cid in zip(sem_docs, sem_metas, sem_dists, sem_ids):
        score = round(1 - dist, 3)
        if score >= min_similarity:
            chunk_map[cid] = {
                "id": cid,
                "text": doc,
                "metadata": meta,
                "semantic_score": score,
            }

    filtered_ids = [cid for cid in sem_ids if cid in chunk_map]

    if not hybrid:
        return [chunk_map[cid] for cid in filtered_ids]

    sem_texts = [chunk_map[cid]["text"] for cid in filtered_ids]
    bm25 = _bm25_scores(question, sem_texts)
    bm25_ranked = [filtered_ids[i] for i in sorted(range(len(bm25)), key=lambda x: bm25[x], reverse=True)]

    merged_ids = _rrf_merge([filtered_ids, bm25_ranked])

    return [chunk_map[cid] for cid in merged_ids if cid in chunk_map]


def rerank(question: str, chunks: list[dict], top_n: int = FINAL_K) -> list[dict]:
    """Rerank chunks using a cross-encoder model and return the top_n."""
    if len(chunks) <= top_n:
        return chunks

    model = _get_rerank_model()
    pairs = [(question, c["text"]) for c in chunks]
    scores = model.predict(pairs).tolist()

    ranked = sorted(zip(scores, chunks), key=lambda x: x[0], reverse=True)
    for score, chunk in ranked:
        chunk["rerank_score"] = round(float(score), 3)

    return [chunk for _, chunk in ranked[:top_n]]


# ---------------------------------------------------------------------------
# Answer generation
# ---------------------------------------------------------------------------

def _build_context(chunks: list[dict]) -> tuple[str, list[dict]]:
    """Build context string and sources list from chunks."""
    context_parts = []
    sources = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk["metadata"]
        title = meta.get("title", "Unknown")
        url = meta.get("url", "")
        score = chunk.get("rerank_score", chunk.get("semantic_score", 0))
        context_parts.append(f"--- Chunk {i} [Source: {title}] ---\n{chunk['text']}")
        sources.append({"title": title, "url": url, "score": score, "text": chunk["text"]})
    return "\n\n".join(context_parts), sources


def ask(
    question: str,
    history: list[dict] | None = None,
    tags: list[str] | None = None,
    use_rerank: bool = True,
    hybrid: bool = True,
    model_id: str | None = None,
    min_similarity: float = 0.0,
    workspace: str | None = None,
    embed_model_id: str | None = None,
) -> dict:
    """Full RAG pipeline. Returns {answer, sources, history}."""
    ui_cfg = config.ui("ask")
    chunks = retrieve(question, top_k=TOP_K, tags=tags, hybrid=hybrid,
                      min_similarity=min_similarity, workspace=workspace,
                      embed_model_id=embed_model_id)

    if not chunks:
        return {
            "answer": ui_cfg.get("empty_kb_message",
                                 "No content has been ingested yet. Add some text or URLs in the Ingest tab first."),
            "sources": [],
            "history": history or [],
        }

    if use_rerank:
        chunks = rerank(question, chunks, top_n=FINAL_K)
    else:
        chunks = chunks[:FINAL_K]

    context, sources = _build_context(chunks)

    messages = list(history or [])
    messages.append({
        "role": "user",
        "content": f"Context:\n{context}\n\nQuestion: {question}",
    })

    client = _get_anthropic()
    used_model = model_id or "claude-sonnet-4-20250514"
    response = client.messages.create(
        model=used_model,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    answer = response.content[0].text
    _track_api_usage(response.usage, used_model, "query")

    updated_history = list(history or [])
    updated_history.append({"role": "user", "content": question})
    updated_history.append({"role": "assistant", "content": answer})

    return {"answer": answer, "sources": sources, "history": updated_history}


def ask_stream(
    question: str,
    history: list[dict] | None = None,
    tags: list[str] | None = None,
    use_rerank: bool = True,
    hybrid: bool = True,
    model_id: str | None = None,
    min_similarity: float = 0.0,
    workspace: str | None = None,
    embed_model_id: str | None = None,
):
    """Streaming version of ask(). Yields (token, sources, updated_history) tuples."""
    ui_cfg = config.ui("ask")
    chunks = retrieve(question, top_k=TOP_K, tags=tags, hybrid=hybrid,
                      min_similarity=min_similarity, workspace=workspace,
                      embed_model_id=embed_model_id)

    if not chunks:
        yield (
            ui_cfg.get("empty_kb_message",
                       "No content has been ingested yet. Add some text or URLs in the Ingest tab first."),
            [],
            history or [],
        )
        return

    if use_rerank:
        chunks = rerank(question, chunks, top_n=FINAL_K)
    else:
        chunks = chunks[:FINAL_K]

    context, sources = _build_context(chunks)

    messages = list(history or [])
    messages.append({
        "role": "user",
        "content": f"Context:\n{context}\n\nQuestion: {question}",
    })

    client = _get_anthropic()
    used_model = model_id or "claude-sonnet-4-20250514"
    full_answer = ""
    with client.messages.stream(
        model=used_model,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            full_answer += text
            yield (text, sources, None)
        final_message = stream.get_final_message()

    _track_api_usage(final_message.usage, used_model, "query-stream")

    updated_history = list(history or [])
    updated_history.append({"role": "user", "content": question})
    updated_history.append({"role": "assistant", "content": full_answer})
    yield ("", sources, updated_history)


def summarise_source(source_id: int) -> str:
    """Generate a bullet-point summary of all chunks for a source."""
    import db as _db
    chunks = _db.get_chunks_for_source(source_id)
    if not chunks:
        return "No chunks found for this source."

    texts = []
    total = 0
    for c in chunks:
        tokens = int(len(c["text"].split()) * 1.3)
        if total + tokens > 3000:
            break
        texts.append(c["text"])
        total += tokens

    combined = "\n\n".join(texts)
    client = _get_anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=512,
        system=SUMMARY_PROMPT,
        messages=[{"role": "user", "content": combined}],
    )
    _track_api_usage(response.usage, "claude-sonnet-4-20250514", "summarise")
    return response.content[0].text


# ---------------------------------------------------------------------------
# Auto-tagging
# ---------------------------------------------------------------------------

AUTO_TAG_PROMPT = """You are a tagging assistant. Given the following text, suggest 3–5 short, lowercase tags
that describe the key topics. Return ONLY a comma-separated list of tags, nothing else.
Example output: python, machine-learning, deployment, aws"""


def suggest_tags(text: str, max_chars: int = 2000) -> list[str]:
    """Use Claude to suggest tags for a piece of content."""
    snippet = text[:max_chars]
    client = _get_anthropic()
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",  # cheap + fast for tagging
        max_tokens=100,
        system=AUTO_TAG_PROMPT,
        messages=[{"role": "user", "content": snippet}],
    )
    raw = response.content[0].text.strip()
    tags = [t.strip().lower().replace(" ", "-") for t in raw.split(",") if t.strip()]
    # Track cost
    _track_api_usage(response.usage, "claude-haiku-4-5-20251001", "auto-tag")
    return tags[:5]


# ---------------------------------------------------------------------------
# Cost / usage tracking
# ---------------------------------------------------------------------------

# Approximate pricing per 1M tokens (USD) — updated as of 2025
_PRICING = {
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.0},
}


def _track_api_usage(usage, model_id: str, operation: str = "query") -> None:
    """Log token usage and estimated cost to the database."""
    import db as _db
    input_tokens = getattr(usage, "input_tokens", 0)
    output_tokens = getattr(usage, "output_tokens", 0)
    pricing = _PRICING.get(model_id, {"input": 3.0, "output": 15.0})
    cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
    _db.log_api_usage(
        model_id=model_id,
        operation=operation,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
    )
