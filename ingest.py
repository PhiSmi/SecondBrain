"""Ingestion pipeline — chunking, embedding, and storage for all content types."""

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import chromadb
import pdfplumber
import requests
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
from youtube_transcript_api import YouTubeTranscriptApi

import config
import db

CHROMA_PATH = Path(__file__).parent / "data" / "chroma"
COLLECTION_NAME = "secondbrain"

_cfg = config.retrieval()
CHUNK_SIZE = _cfg.get("chunk_size", 500)
CHUNK_OVERLAP = _cfg.get("chunk_overlap", 50)
MIN_CONTENT_LENGTH = 200

_models: dict[str, SentenceTransformer] = {}
_collections: dict[str, chromadb.Collection] = {}


def _get_model(model_id: str | None = None) -> SentenceTransformer:
    model_id = model_id or "all-MiniLM-L6-v2"
    if model_id not in _models:
        _models[model_id] = SentenceTransformer(model_id)
    return _models[model_id]


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


def extract_pdf_text(file_bytes: bytes, ocr: bool = False) -> str:
    """Extract text from a PDF file (bytes). Falls back to OCR if enabled and text is sparse."""
    import io
    text_parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

    text = "\n\n".join(text_parts)

    # If we got very little text and OCR is enabled, try OCR
    if ocr and len(text.split()) < 50:
        try:
            import pytesseract
            from PIL import Image
            from pdf2image import convert_from_bytes
            images = convert_from_bytes(file_bytes, dpi=300)
            ocr_parts = []
            for img in images:
                ocr_text = pytesseract.image_to_string(img)
                if ocr_text.strip():
                    ocr_parts.append(ocr_text.strip())
            if ocr_parts:
                text = "\n\n".join(ocr_parts)
        except ImportError:
            pass  # OCR deps not installed — return what we have
    return text


def extract_docx_text(file_bytes: bytes) -> str:
    """Extract text from a DOCX file (bytes)."""
    import io
    import zipfile
    from xml.etree import ElementTree

    with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
        xml_content = z.read("word/document.xml")
    tree = ElementTree.fromstring(xml_content)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []
    for p in tree.iter(f"{{{ns['w']}}}p"):
        texts = [t.text for t in p.iter(f"{{{ns['w']}}}t") if t.text]
        if texts:
            paragraphs.append("".join(texts))
    return "\n\n".join(paragraphs)


def fetch_youtube_transcript(url: str) -> str:
    """Extract transcript text from a YouTube URL."""
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

    transcript_list = YouTubeTranscriptApi().fetch(video_id)
    text = " ".join(entry.text for entry in transcript_list)
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Chunking — markdown-aware recursive splitter
# ---------------------------------------------------------------------------

def _approx_tokens(text: str) -> int:
    return int(len(text.split()) * 1.3)


# Patterns for detecting protected blocks that should not be split
_CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_TABLE_RE = re.compile(r"(?:^\|.+\|$\n?){2,}", re.MULTILINE)


def _protect_blocks(text: str) -> tuple[str, dict[str, str]]:
    """Replace code blocks and tables with placeholders so they aren't split."""
    placeholders: dict[str, str] = {}
    counter = 0

    def _replace(match: re.Match) -> str:
        nonlocal counter
        key = f"\x00BLOCK_{counter}\x00"
        placeholders[key] = match.group(0)
        counter += 1
        return key

    text = _CODE_BLOCK_RE.sub(_replace, text)
    text = _TABLE_RE.sub(_replace, text)
    return text, placeholders


def _restore_blocks(chunks: list[str], placeholders: dict[str, str]) -> list[str]:
    """Restore protected blocks from placeholders."""
    if not placeholders:
        return chunks
    restored = []
    for chunk in chunks:
        for key, value in placeholders.items():
            chunk = chunk.replace(key, value)
        restored.append(chunk)
    return restored


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Markdown-aware recursive chunker.

    Preserves code blocks and tables as atomic units, then splits on:
    1. Markdown headings (# ## ###)
    2. Blank lines (paragraphs)
    3. Sentence boundaries
    4. Words (last resort)
    """
    protected_text, placeholders = _protect_blocks(text)
    chunks = _recursive_split(protected_text, chunk_size, overlap)
    return _restore_blocks(chunks, placeholders)


def _recursive_split(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text using progressively finer boundaries until chunks fit."""
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
        return [text.strip()]

    sep = separators[0]
    parts = [p for p in re.split(sep, text) if p.strip()]

    if len(parts) <= 1:
        return _split_with_separator(text, separators[1:], chunk_size, overlap)

    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0
    overlap_words: list[str] = []

    for part in parts:
        part_tokens = _approx_tokens(part)

        if part_tokens > chunk_size:
            if current:
                chunks.append("\n\n".join(current))
                overlap_words = " ".join(current).split()[-int(overlap / 1.3):]
                current = []
                current_tokens = 0
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
    workspace: str | None = None,
    embed_model_id: str | None = None,
) -> int:
    """Embed chunks and write to ChromaDB + SQLite. Returns source_id."""
    model = _get_model(embed_model_id)
    collection = _get_collection(workspace)

    embeddings = model.encode(chunks, show_progress_bar=False).tolist()

    source_id = db.log_source(
        title=title, source_type=source_type, url=url,
        chunk_count=len(chunks), tags=tags,
        workspace=workspace or config.workspaces().get("default", "default"),
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
    workspace: str | None = None,
    embed_model_id: str | None = None,
) -> int:
    """Chunk, embed and store raw text. Returns chunk count."""
    chunks = chunk_text(text)
    if not chunks:
        return 0
    _embed_and_store(chunks, title, source_type, url, tags, workspace, embed_model_id)
    return len(chunks)


def ingest_url(
    url: str,
    title: str | None = None,
    tags: list[str] | None = None,
    workspace: str | None = None,
    embed_model_id: str | None = None,
) -> tuple[int, bool]:
    """Fetch a URL, extract text and ingest it. Returns (chunk_count, js_warning)."""
    text, js_warning = fetch_url_text(url)
    chunk_count = ingest_text(text, title=title or url, source_type="url", url=url, tags=tags,
                              workspace=workspace, embed_model_id=embed_model_id)
    return chunk_count, js_warning


def ingest_pdf(
    file_bytes: bytes,
    title: str,
    tags: list[str] | None = None,
    workspace: str | None = None,
    embed_model_id: str | None = None,
    ocr: bool = False,
) -> int:
    """Extract text from a PDF and ingest it. Returns chunk count."""
    text = extract_pdf_text(file_bytes, ocr=ocr)
    return ingest_text(text, title=title, source_type="pdf", tags=tags,
                       workspace=workspace, embed_model_id=embed_model_id)


def ingest_docx(
    file_bytes: bytes,
    title: str,
    tags: list[str] | None = None,
    workspace: str | None = None,
    embed_model_id: str | None = None,
) -> int:
    """Extract text from a DOCX and ingest it. Returns chunk count."""
    text = extract_docx_text(file_bytes)
    return ingest_text(text, title=title, source_type="docx", tags=tags,
                       workspace=workspace, embed_model_id=embed_model_id)


def ingest_file(
    file_bytes: bytes,
    filename: str,
    title: str,
    tags: list[str] | None = None,
    workspace: str | None = None,
    embed_model_id: str | None = None,
    ocr: bool = False,
) -> int:
    """Ingest a file based on its extension. Returns chunk count."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "pdf":
        return ingest_pdf(file_bytes, title=title, tags=tags, workspace=workspace,
                          embed_model_id=embed_model_id, ocr=ocr)
    elif ext == "docx":
        return ingest_docx(file_bytes, title=title, tags=tags, workspace=workspace,
                           embed_model_id=embed_model_id)
    else:
        text = file_bytes.decode("utf-8", errors="replace")
        return ingest_text(text, title=title, source_type="file", tags=tags,
                           workspace=workspace, embed_model_id=embed_model_id)


def ingest_youtube(
    url: str,
    title: str | None = None,
    tags: list[str] | None = None,
    workspace: str | None = None,
    embed_model_id: str | None = None,
) -> int:
    """Fetch a YouTube transcript and ingest it. Returns chunk count."""
    text = fetch_youtube_transcript(url)
    return ingest_text(text, title=title or url, source_type="youtube", url=url, tags=tags,
                       workspace=workspace, embed_model_id=embed_model_id)


def ingest_bulk_urls(
    urls: list[str],
    tags: list[str] | None = None,
    workspace: str | None = None,
    embed_model_id: str | None = None,
) -> list[dict]:
    """Ingest a list of URLs. Returns a result list with status per URL."""
    results = []
    for url in urls:
        url = url.strip()
        if not url:
            continue
        try:
            count, js_warning = ingest_url(url, tags=tags, workspace=workspace,
                                           embed_model_id=embed_model_id)
            results.append({"url": url, "chunks": count, "warning": js_warning, "error": None})
        except Exception as e:
            results.append({"url": url, "chunks": 0, "warning": False, "error": str(e)})
    return results


def fetch_rss_feed(feed_url: str) -> list[dict]:
    """Fetch an RSS/Atom feed and return a list of entries.

    Each entry: {id, title, link, summary, published}.
    """
    import feedparser
    feed = feedparser.parse(feed_url)
    entries = []
    for entry in feed.entries:
        entries.append({
            "id": getattr(entry, "id", entry.get("link", "")),
            "title": getattr(entry, "title", "Untitled"),
            "link": getattr(entry, "link", ""),
            "summary": getattr(entry, "summary", ""),
            "published": getattr(entry, "published", ""),
        })
    return entries


def ingest_rss_feed(feed_id: int) -> dict:
    """Fetch new entries from an RSS feed and ingest them.

    Returns {new_entries, total_chunks, errors}.
    """
    feeds = db.get_rss_feeds()
    feed = next((f for f in feeds if f["id"] == feed_id), None)
    if not feed:
        return {"new_entries": 0, "total_chunks": 0, "errors": ["Feed not found"]}

    try:
        entries = fetch_rss_feed(feed["url"])
    except Exception as e:
        return {"new_entries": 0, "total_chunks": 0, "errors": [str(e)]}

    last_id = feed.get("last_entry_id")
    new_entries = 0
    total_chunks = 0
    errors = []

    for entry in entries:
        if last_id and entry["id"] == last_id:
            break  # Already seen this entry and everything after it

        # Try to fetch full article text, fall back to summary
        text = ""
        if entry["link"]:
            try:
                text, _ = fetch_url_text(entry["link"])
            except Exception:
                text = entry.get("summary", "")
        if not text:
            text = entry.get("summary", "")
        if not text.strip():
            continue

        try:
            n = ingest_text(
                text,
                title=entry["title"],
                source_type="rss",
                url=entry["link"],
                tags=feed.get("tags"),
                workspace=feed.get("workspace", "default"),
            )
            total_chunks += n
            new_entries += 1
        except Exception as e:
            errors.append(f"{entry['title']}: {e}")

    # Update last fetched
    if entries:
        db.update_rss_feed_fetched(feed_id, entries[0]["id"])

    return {"new_entries": new_entries, "total_chunks": total_chunks, "errors": errors}


def delete_source(source_id: int, workspace: str | None = None) -> None:
    """Delete a source and all its vectors from ChromaDB and SQLite."""
    collection = _get_collection(workspace)
    chroma_ids = db.get_chroma_ids_for_source(source_id)
    if chroma_ids:
        collection.delete(ids=chroma_ids)
    db.delete_source(source_id)


def export_knowledge_base(workspace: str | None = None) -> dict:
    """Export the entire knowledge base as a JSON-serialisable dict."""
    sources = db.get_all_sources(workspace=workspace)
    export_data = {
        "version": 1,
        "workspace": workspace or "default",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "sources": [],
    }

    for src in sources:
        chunks = db.get_chunks_for_source(src["id"])
        export_data["sources"].append({
            "title": src["title"],
            "source_type": src["source_type"],
            "url": src.get("url"),
            "tags": src.get("tags", []),
            "ingested_at": src["ingested_at"],
            "chunks": [{"text": c["text"], "chunk_index": c["chunk_index"]} for c in chunks],
        })
    return export_data


def import_knowledge_base(data: dict, workspace: str | None = None) -> dict:
    """Import a previously exported knowledge base. Returns summary stats."""
    imported = 0
    skipped = 0
    ws = workspace or data.get("workspace", "default")
    existing_titles = {s["title"] for s in db.get_all_sources(workspace=ws)}

    for src in data.get("sources", []):
        if src["title"] in existing_titles:
            skipped += 1
            continue

        chunks_text = [c["text"] for c in src.get("chunks", [])]
        if not chunks_text:
            skipped += 1
            continue

        _embed_and_store(
            chunks_text,
            title=src["title"],
            source_type=src.get("source_type", "text"),
            url=src.get("url"),
            tags=src.get("tags"),
            workspace=ws,
        )
        imported += 1

    return {"imported": imported, "skipped": skipped}


def find_duplicate_chunks(threshold: float | None = None, workspace: str | None = None) -> list[dict]:
    """Find near-duplicate chunks using cosine similarity. Returns pairs above threshold."""
    if threshold is None:
        threshold = config.retrieval().get("dedup_threshold", 0.95)
    collection = _get_collection(workspace)
    total = collection.count()
    if total < 2:
        return []

    limit = min(total, 500)
    all_data = collection.get(limit=limit, include=["documents", "metadatas", "embeddings"])

    if not all_data["embeddings"]:
        return []

    import numpy as np
    embeddings = np.array(all_data["embeddings"])
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1
    normed = embeddings / norms
    sim_matrix = normed @ normed.T

    duplicates = []
    seen = set()
    for i in range(len(sim_matrix)):
        for j in range(i + 1, len(sim_matrix)):
            if sim_matrix[i][j] >= threshold:
                pair_key = (all_data["ids"][i], all_data["ids"][j])
                if pair_key not in seen:
                    seen.add(pair_key)
                    duplicates.append({
                        "chunk_a_id": all_data["ids"][i],
                        "chunk_b_id": all_data["ids"][j],
                        "title_a": all_data["metadatas"][i].get("title", "Unknown"),
                        "title_b": all_data["metadatas"][j].get("title", "Unknown"),
                        "similarity": round(float(sim_matrix[i][j]), 4),
                        "text_a": all_data["documents"][i][:200],
                        "text_b": all_data["documents"][j][:200],
                    })
    return sorted(duplicates, key=lambda x: x["similarity"], reverse=True)[:50]


def check_url_freshness(source_id: int) -> dict:
    """Check if a URL source's content has changed since last ingest.

    Returns dict with keys: changed (bool), old_length, new_length, error (str|None).
    """
    sources = [s for s in db.get_all_sources() if s["id"] == source_id]
    if not sources:
        return {"changed": False, "error": "Source not found"}
    src = sources[0]
    if not src.get("url"):
        return {"changed": False, "error": "Source has no URL"}

    try:
        new_text, _ = fetch_url_text(src["url"])
    except Exception as e:
        return {"changed": False, "error": str(e)}

    old_chunks = db.get_chunks_for_source(source_id)
    old_text = " ".join(c["text"] for c in old_chunks)

    old_len = len(old_text.split())
    new_len = len(new_text.split())
    # Consider changed if word count differs by more than 10%
    changed = abs(new_len - old_len) / max(old_len, 1) > 0.10

    return {"changed": changed, "old_length": old_len, "new_length": new_len, "error": None}


def recrawl_source(source_id: int, workspace: str | None = None) -> dict:
    """Re-fetch a URL source and re-ingest if content changed.

    Returns dict: {changed, chunks, error}.
    """
    sources = [s for s in db.get_all_sources() if s["id"] == source_id]
    if not sources:
        return {"changed": False, "chunks": 0, "error": "Source not found"}
    src = sources[0]
    if not src.get("url"):
        return {"changed": False, "chunks": 0, "error": "Source has no URL"}

    freshness = check_url_freshness(source_id)
    if freshness.get("error"):
        return {"changed": False, "chunks": 0, "error": freshness["error"]}
    if not freshness["changed"]:
        return {"changed": False, "chunks": 0, "error": None}

    # Delete old and re-ingest
    delete_source(source_id, workspace=workspace)
    try:
        count, _ = ingest_url(src["url"], title=src["title"], tags=src.get("tags"),
                              workspace=workspace)
        return {"changed": True, "chunks": count, "error": None}
    except Exception as e:
        return {"changed": True, "chunks": 0, "error": str(e)}


def reingest_source(source_id: int, workspace: str | None = None,
                    embed_model_id: str | None = None) -> int:
    """Re-embed and re-store all chunks for an existing source.

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

    collection = _get_collection(workspace)
    old_ids = [r["chroma_id"] for r in chunks_rows]
    collection.delete(ids=old_ids)

    texts = [r["text"] for r in chunks_rows]
    model = _get_model(embed_model_id)
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
