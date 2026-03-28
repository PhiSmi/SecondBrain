"""Chunking + embedding pipeline for ingesting text and URLs into ChromaDB."""

import re
import uuid
from pathlib import Path

import chromadb
import requests
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer

import db

CHROMA_PATH = Path(__file__).parent / "data" / "chroma"
COLLECTION_NAME = "secondbrain"
CHUNK_SIZE = 500  # target tokens (approx words * 1.3)
CHUNK_OVERLAP = 50

# Lazy-loaded singletons
_model: SentenceTransformer | None = None
_collection: chromadb.Collection | None = None


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


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def fetch_url_text(url: str) -> str:
    """Download a URL and extract the main text content."""
    resp = requests.get(url, timeout=15, headers={"User-Agent": "SecondBrain/1.0"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove non-content elements
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    # Collapse whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def _approx_token_count(text: str) -> int:
    """Rough token estimate: word count * 1.3."""
    return int(len(text.split()) * 1.3)


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into chunks of approximately `chunk_size` tokens with overlap."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: list[str] = []
    current_chunk: list[str] = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = _approx_token_count(para)

        # If a single paragraph exceeds chunk_size, split by sentences
        if para_tokens > chunk_size:
            sentences = re.split(r"(?<=[.!?])\s+", para)
            for sentence in sentences:
                sent_tokens = _approx_token_count(sentence)
                if current_tokens + sent_tokens > chunk_size and current_chunk:
                    chunks.append(" ".join(current_chunk))
                    # Keep overlap worth of text
                    overlap_text = " ".join(current_chunk)
                    overlap_words = overlap_text.split()[-int(overlap / 1.3) :]
                    current_chunk = [" ".join(overlap_words)] if overlap_words else []
                    current_tokens = _approx_token_count(" ".join(current_chunk))
                current_chunk.append(sentence)
                current_tokens += sent_tokens
        else:
            if current_tokens + para_tokens > chunk_size and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                overlap_text = current_chunk[-1] if current_chunk else ""
                current_chunk = [overlap_text] if _approx_token_count(overlap_text) <= overlap else []
                current_tokens = _approx_token_count("\n\n".join(current_chunk))
            current_chunk.append(para)
            current_tokens += para_tokens

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return chunks


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

def ingest_text(text: str, title: str, source_type: str = "text", url: str | None = None) -> int:
    """Chunk, embed, and store text. Returns the number of chunks created."""
    chunks = chunk_text(text)
    if not chunks:
        return 0

    model = _get_model()
    collection = _get_collection()

    # Generate embeddings
    embeddings = model.encode(chunks, show_progress_bar=False).tolist()

    # Build IDs and metadata
    source_id = db.log_source(title=title, source_type=source_type, url=url, chunk_count=len(chunks))
    ids = [f"{source_id}_{i}_{uuid.uuid4().hex[:8]}" for i in range(len(chunks))]
    metadatas = [
        {"source_id": source_id, "title": title, "url": url or "", "chunk_index": i}
        for i in range(len(chunks))
    ]

    collection.add(documents=chunks, embeddings=embeddings, ids=ids, metadatas=metadatas)
    return len(chunks)


def ingest_url(url: str, title: str | None = None) -> int:
    """Fetch a URL, extract text, and ingest it. Returns chunk count."""
    text = fetch_url_text(url)
    if not title:
        title = url
    return ingest_text(text, title=title, source_type="url", url=url)
