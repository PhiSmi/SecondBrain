"""Retrieval + Claude answer generation pipeline.

Supports:
- Semantic search (dense embeddings via sentence-transformers)
- Hybrid search (semantic + BM25 keyword, merged via Reciprocal Rank Fusion)
- Tag-scoped retrieval
- Cross-encoder reranking
- Multi-turn conversation history
- Source summarisation
"""

import math
import os
import re
from collections import defaultdict
from pathlib import Path

import anthropic
import chromadb
from dotenv import load_dotenv
from sentence_transformers import CrossEncoder, SentenceTransformer

load_dotenv(Path(__file__).parent / ".env", override=False)

CHROMA_PATH = Path(__file__).parent / "data" / "chroma"
COLLECTION_NAME = "secondbrain"
TOP_K = 10          # retrieve more, then rerank down to FINAL_K
FINAL_K = 5         # chunks sent to Claude after reranking
RRF_K = 60          # constant for Reciprocal Rank Fusion

_embed_model: SentenceTransformer | None = None
_rerank_model: CrossEncoder | None = None
_collection: chromadb.Collection | None = None
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


def _get_embed_model() -> SentenceTransformer:
    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embed_model


def _get_rerank_model() -> CrossEncoder:
    global _rerank_model
    if _rerank_model is None:
        # Lightweight cross-encoder — runs on CPU, ~85MB
        _rerank_model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _rerank_model


def _get_collection() -> chromadb.Collection:
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


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

    # IDF for each query term
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
) -> list[dict]:
    """Retrieve the top-k most relevant chunks.

    Args:
        question: The user's question.
        top_k: Number of candidates to retrieve before reranking.
        tags: If provided, only return chunks from sources with these tags.
        hybrid: If True, merge semantic + BM25 results via RRF.

    Returns:
        List of chunk dicts with keys: id, text, metadata, semantic_score.
    """
    model = _get_embed_model()
    collection = _get_collection()

    total = collection.count()
    if total == 0:
        return []

    n = min(top_k, total)

    # Build ChromaDB where clause for tag filtering
    where: dict | None = None
    if tags:
        # ChromaDB metadata stores tags as comma-separated string
        # Use $or across individual tag matches
        where = {"$or": [{"tags": {"$contains": tag}} for tag in tags]} if len(tags) > 1 else {"tags": {"$contains": tags[0]}}

    # --- Semantic retrieval ---
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

    # Build a lookup: id → {text, metadata, semantic_score}
    chunk_map: dict[str, dict] = {}
    for doc, meta, dist, cid in zip(sem_docs, sem_metas, sem_dists, sem_ids):
        chunk_map[cid] = {
            "id": cid,
            "text": doc,
            "metadata": meta,
            "semantic_score": round(1 - dist, 3),
        }

    if not hybrid:
        return [chunk_map[cid] for cid in sem_ids]

    # --- BM25 retrieval over the same candidate set ---
    sem_texts = [chunk_map[cid]["text"] for cid in sem_ids]
    bm25 = _bm25_scores(question, sem_texts)
    bm25_ranked = [sem_ids[i] for i in sorted(range(len(bm25)), key=lambda x: bm25[x], reverse=True)]

    # Merge via RRF
    merged_ids = _rrf_merge([sem_ids, bm25_ranked])

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

def ask(
    question: str,
    history: list[dict] | None = None,
    tags: list[str] | None = None,
    use_rerank: bool = True,
    hybrid: bool = True,
) -> dict:
    """Full RAG pipeline. Returns {answer, sources, history}.

    Args:
        question: The user's question.
        history: Prior conversation turns [{role, content}, ...].
        tags: Restrict retrieval to sources with these tags.
        use_rerank: Whether to apply cross-encoder reranking.
        hybrid: Whether to use hybrid BM25 + semantic search.
    """
    chunks = retrieve(question, top_k=TOP_K, tags=tags, hybrid=hybrid)

    if not chunks:
        return {
            "answer": "No content has been ingested yet. Add some text or URLs in the Ingest tab first.",
            "sources": [],
            "history": history or [],
        }

    if use_rerank:
        chunks = rerank(question, chunks, top_n=FINAL_K)
    else:
        chunks = chunks[:FINAL_K]

    # Build context
    context_parts = []
    sources = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk["metadata"]
        title = meta.get("title", "Unknown")
        url = meta.get("url", "")
        score = chunk.get("rerank_score", chunk.get("semantic_score", 0))
        context_parts.append(f"--- Chunk {i} [Source: {title}] ---\n{chunk['text']}")
        sources.append({"title": title, "url": url, "score": score, "text": chunk["text"]})

    context = "\n\n".join(context_parts)

    # Build message history
    messages = list(history or [])
    messages.append({
        "role": "user",
        "content": f"Context:\n{context}\n\nQuestion: {question}",
    })

    client = _get_anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    answer = response.content[0].text

    # Append assistant turn to history (with clean question, not the context blob)
    updated_history = list(history or [])
    updated_history.append({"role": "user", "content": question})
    updated_history.append({"role": "assistant", "content": answer})

    return {"answer": answer, "sources": sources, "history": updated_history}


def summarise_source(source_id: int) -> str:
    """Generate a bullet-point summary of all chunks for a source."""
    import db as _db
    chunks = _db.get_chunks_for_source(source_id)
    if not chunks:
        return "No chunks found for this source."

    # Concatenate up to ~3000 tokens worth of text to keep cost low
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
    return response.content[0].text
