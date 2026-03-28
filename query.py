"""Retrieval + Claude answer generation pipeline."""

import os
from pathlib import Path

import anthropic
import chromadb
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

load_dotenv(Path(__file__).parent / ".env")

CHROMA_PATH = Path(__file__).parent / "data" / "chroma"
COLLECTION_NAME = "secondbrain"
TOP_K = 5

_model: SentenceTransformer | None = None
_collection: chromadb.Collection | None = None
_client: anthropic.Anthropic | None = None

SYSTEM_PROMPT = """You are a helpful research assistant. Answer the user's question based ONLY on the provided context chunks. Follow these rules strictly:

1. Only use information from the provided context to answer.
2. Cite your sources by referencing the chunk's title in square brackets, e.g. [Source Title].
3. If the context does not contain enough information to answer the question, say "I don't have enough information in my knowledge base to answer this question." and suggest what kind of content might help.
4. Be concise and direct. Use bullet points for multi-part answers.
5. If multiple sources discuss the same topic, synthesize them and cite all relevant sources."""


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


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


def retrieve(question: str, top_k: int = TOP_K) -> dict:
    """Embed the question and retrieve the top-k most similar chunks from ChromaDB."""
    model = _get_model()
    collection = _get_collection()

    query_embedding = model.encode([question], show_progress_bar=False).tolist()

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=min(top_k, collection.count()) if collection.count() > 0 else 1,
        include=["documents", "metadatas", "distances"],
    )

    return results


def ask(question: str, top_k: int = TOP_K) -> dict:
    """Full RAG pipeline: retrieve context, build prompt, call Claude, return answer + sources."""
    results = retrieve(question, top_k)

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    if not documents:
        return {
            "answer": "No content has been ingested yet. Add some text or URLs in the Ingest tab first.",
            "sources": [],
        }

    # Build context block
    context_parts = []
    sources = []
    for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances)):
        title = meta.get("title", "Unknown")
        url = meta.get("url", "")
        similarity = 1 - dist  # cosine distance to similarity
        context_parts.append(f"--- Chunk {i+1} [Source: {title}] (similarity: {similarity:.2f}) ---\n{doc}")
        sources.append({"title": title, "url": url, "similarity": round(similarity, 3), "text": doc})

    context = "\n\n".join(context_parts)

    # Call Claude
    client = _get_anthropic()
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {question}",
            }
        ],
    )

    answer = message.content[0].text

    return {"answer": answer, "sources": sources}
