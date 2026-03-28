"""Ingestion pipeline — chunking, embedding, and storage for all content types."""

import re
import uuid
from pathlib import Path

import chromadb
import pdfplumber
import requests
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
from youtube_transcript_api import YouTubeTranscriptApi

import db

CHROMA_PATH = Path(__file__).parent / "data" / "chroma"
COLLECTION_NAME = "secondbrain"
CHUNK_SIZE = 500       # target tokens (~words * 1.3)
CHUNK_OVERLAP = 50
MIN_CONTENT_LENGTH = 200

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

def fetch_url_text(url: str) -> tuple[str, bool]:
    """Download a URL and extract main text. Returns (text, js_warning)."""
    resp = requests.get(
        url,
        timeout=15,
        headers={"User-Agent": "Mozilla/5.0 (compatible; SecondBrain/1.0)"},
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
        tag.decompose()

    content = (
        soup.find("article")
        or soup.find("main")
        or soup.find(attrs={"role": "main"})
        or soup.find(id=re.compile(r"(content|article|main|body)", re.I))
        or soup.find(class_=re.compile(r"(article|post|content|story|body)", re.I))
    )

    if content:
        text = content.get_text(separator="\n")
    else:
        paragraphs = soup.find_all("p")
        text = "\n\n".join(p.get_text() for p in paragraphs) if paragraphs else soup.get_text(separator="\n")

    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = text.strip()
    return text, len(text) < MIN_CONTENT_LENGTH


def extract_pdf_text(file_bytes: bytes) -> str:
    """Extract text from a PDF file (bytes)."""
    import io
    text_parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n\n".join(text_parts)


def fetch_youtube_transcript(url: str) -> str:
    """Extract transcript text from a YouTube URL."""
    # Extract video ID from various YouTube URL formats
    patterns = [
        r"(?:v=|youtu\.be/|embed/)([A-Za-z0-9_-]{11})",
    ]
    video_id = None
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            video_id = match.group(1)
            break
    if not video_id:
        raise ValueError(f"Could not extract video ID from URL: {url}")

    transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
    text = " ".join(entry["text"] for entry in transcript_list)
    # Clean up auto-generated transcript artefacts
    text = re.sub(r"\[.*?\]", "", text)   # remove [Music], [Applause] etc.
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Chunking — recursive splitter
# ---------------------------------------------------------------------------

def _approx_tokens(text: str) -> int:
    return int(len(text.split()) * 1.3)


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Recursive chunker that respects headings, then paragraphs, then sentences.

    Strategy:
    1. Split on markdown/heading boundaries first (# ## ### or blank-line-separated blocks)
    2. If a section still exceeds chunk_size, split by paragraphs
    3. If a paragraph still exceeds chunk_size, split by sentences
    4. Carry overlap tokens into the next chunk at every level
    """
    return _recursive_split(text, chunk_size, overlap)


def _recursive_split(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text using progressively finer boundaries until chunks fit."""
    # Separators tried in order — most structural first
    separators = [
        r"\n#{1,6} ",           # markdown headings
        r"\n\n",                # blank lines (paragraphs)
        r"(?<=[.!?])\s+",       # sentence boundaries
        r" ",                   # words (last resort)
    ]
    return _split_with_separator(text, separators, chunk_size, overlap)


def _split_with_separator(text: str, separators: list[str], chunk_size: int, overlap: int) -> list[str]:
    if not text.strip():
        return []

    if _approx_tokens(text) <= chunk_size:
        return [text.strip()]

    if not separators:
        # Can't split further — return as-is even if oversized
        return [text.strip()]

    sep = separators[0]
    parts = [p for p in re.split(sep, text) if p.strip()]

    if len(parts) <= 1:
        # This separator didn't help — try the next one
        return _split_with_separator(text, separators[1:], chunk_size, overlap)

    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0
    overlap_words: list[str] = []

    for part in parts:
        part_tokens = _approx_tokens(part)

        if part_tokens > chunk_size:
            # Flush current buffer first
            if current:
                chunks.append("\n\n".join(current))
                overlap_words = " ".join(current).split()[-int(overlap / 1.3):]
                current = []
                current_tokens = 0
            # Recursively split the oversized part with finer separators
            sub_chunks = _split_with_separator(part, separators[1:], chunk_size, overlap)
            chunks.extend(sub_chunks)
            if sub_chunks:
                overlap_words = sub_chunks[-1].split()[-int(overlap / 1.3):]
            continue

        if current_tokens + part_tokens > chunk_size and current:
            chunks.append("\n\n".join(current))
            overlap_words = " ".join(current).split()[-int(overlap / 1.3):]
            current = []
            current_tokens = 0

        # Prepend overlap text to new chunk
        if not current and overlap_words:
            overlap_text = " ".join(overlap_words)
            current = [overlap_text]
            current_tokens = _approx_tokens(overlap_text)

        current.append(part)
        current_tokens += part_tokens

    if current:
        chunks.append("\n\n".join(current))

    return [c for c in chunks if c.strip()]


# ---------------------------------------------------------------------------
# Core ingestion
# ---------------------------------------------------------------------------

def _embed_and_store(
    chunks: list[str],
    title: str,
    source_type: str,
    url: str | None,
    tags: list[str] | None,
) -> int:
    """Embed chunks and write to ChromaDB + SQLite. Returns source_id."""
    model = _get_model()
    collection = _get_collection()

    embeddings = model.encode(chunks, show_progress_bar=False).tolist()

    source_id = db.log_source(
        title=title, source_type=source_type, url=url,
        chunk_count=len(chunks), tags=tags,
    )
    chroma_ids = [f"{source_id}_{i}_{uuid.uuid4().hex[:8]}" for i in range(len(chunks))]
    tag_str = ",".join(tags) if tags else ""
    metadatas = [
        {"source_id": source_id, "title": title, "url": url or "", "chunk_index": i, "tags": tag_str}
        for i in range(len(chunks))
    ]

    collection.add(documents=chunks, embeddings=embeddings, ids=chroma_ids, metadatas=metadatas)
    db.log_chunks(source_id, chroma_ids, chunks)
    return source_id


def ingest_text(
    text: str,
    title: str,
    source_type: str = "text",
    url: str | None = None,
    tags: list[str] | None = None,
) -> int:
    """Chunk, embed and store raw text. Returns chunk count."""
    chunks = chunk_text(text)
    if not chunks:
        return 0
    _embed_and_store(chunks, title, source_type, url, tags)
    return len(chunks)


def ingest_url(
    url: str,
    title: str | None = None,
    tags: list[str] | None = None,
) -> tuple[int, bool]:
    """Fetch a URL, extract text and ingest it. Returns (chunk_count, js_warning)."""
    text, js_warning = fetch_url_text(url)
    chunk_count = ingest_text(text, title=title or url, source_type="url", url=url, tags=tags)
    return chunk_count, js_warning


def ingest_pdf(
    file_bytes: bytes,
    title: str,
    tags: list[str] | None = None,
) -> int:
    """Extract text from a PDF and ingest it. Returns chunk count."""
    text = extract_pdf_text(file_bytes)
    return ingest_text(text, title=title, source_type="pdf", tags=tags)


def ingest_youtube(
    url: str,
    title: str | None = None,
    tags: list[str] | None = None,
) -> int:
    """Fetch a YouTube transcript and ingest it. Returns chunk count."""
    text = fetch_youtube_transcript(url)
    return ingest_text(text, title=title or url, source_type="youtube", url=url, tags=tags)


def ingest_bulk_urls(
    urls: list[str],
    tags: list[str] | None = None,
) -> list[dict]:
    """Ingest a list of URLs. Returns a result list with status per URL."""
    results = []
    for url in urls:
        url = url.strip()
        if not url:
            continue
        try:
            count, js_warning = ingest_url(url, tags=tags)
            results.append({"url": url, "chunks": count, "warning": js_warning, "error": None})
        except Exception as e:
            results.append({"url": url, "chunks": 0, "warning": False, "error": str(e)})
    return results


def delete_source(source_id: int) -> None:
    """Delete a source and all its vectors from ChromaDB and SQLite."""
    collection = _get_collection()
    chroma_ids = db.get_chroma_ids_for_source(source_id)
    if chroma_ids:
        collection.delete(ids=chroma_ids)
    db.delete_source(source_id)


def reingest_source(source_id: int) -> int:
    """Re-embed and re-store all chunks for an existing source (e.g. after model change).

    Deletes existing vectors, re-embeds stored chunk text, writes new vectors.
    Returns the chunk count.
    """
    chunks_rows = db.get_chunks_for_source(source_id)
    if not chunks_rows:
        return 0

    sources = [s for s in db.get_all_sources() if s["id"] == source_id]
    if not sources:
        return 0
    src = sources[0]

    # Remove old vectors
    collection = _get_collection()
    old_ids = [r["chroma_id"] for r in chunks_rows]
    collection.delete(ids=old_ids)

    # Re-embed
    texts = [r["text"] for r in chunks_rows]
    model = _get_model()
    embeddings = model.encode(texts, show_progress_bar=False).tolist()
    new_ids = [f"{source_id}_{i}_{uuid.uuid4().hex[:8]}" for i in range(len(texts))]
    tag_str = ",".join(src.get("tags") or [])
    metadatas = [
        {
            "source_id": source_id,
            "title": src["title"],
            "url": src.get("url") or "",
            "chunk_index": i,
            "tags": tag_str,
        }
        for i in range(len(texts))
    ]
    collection.add(documents=texts, embeddings=embeddings, ids=new_ids, metadatas=metadatas)

    # Update stored chroma IDs in SQLite
    conn_rows = db.get_chunks_for_source(source_id)
    import sqlite3
    conn = sqlite3.connect(str(db.DB_PATH))
    for old_row, new_id in zip(conn_rows, new_ids):
        conn.execute("UPDATE chunks SET chroma_id = ? WHERE id = ?", (new_id, old_row["id"]))
    conn.commit()
    conn.close()

    return len(texts)
