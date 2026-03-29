"""Ingestion pipeline — chunking, embedding, and storage for all content types."""

from __future__ import annotations

import logging
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
MIN_CONTENT_LENGTH = 200

logger = logging.getLogger(__name__)
_models: dict[str, SentenceTransformer] = {}
_collections: dict[str, chromadb.Collection] = {}
_client: chromadb.PersistentClient | None = None


def _retrieval_setting(key: str, default):
    return config.retrieval().get(key, default)


def _ingestion_setting(key: str, default):
    return config.ingestion().get(key, default)


def _default_embed_model_id() -> str:
    return config.default_embedding_model()


def _normalise_model_id(model_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", model_id).strip("_").lower()


def _legacy_collection_name(workspace: str | None = None) -> str:
    ws = workspace or config.workspaces().get("default", "default")
    return f"secondbrain_{ws}" if ws != "default" else COLLECTION_NAME


def _get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    return _client


def _get_model(model_id: str | None = None) -> SentenceTransformer:
    model_id = model_id or _default_embed_model_id()
    if model_id not in _models:
        _models[model_id] = SentenceTransformer(model_id)
    return _models[model_id]


def _collection_name(workspace: str | None = None, embed_model_id: str | None = None) -> str:
    ws = workspace or config.workspaces().get("default", "default")
    model = _normalise_model_id(embed_model_id or _default_embed_model_id())
    base = f"secondbrain_{ws}" if ws != "default" else COLLECTION_NAME
    return f"{base}_{model}"


def _get_collection(
    workspace: str | None = None,
    embed_model_id: str | None = None,
) -> chromadb.Collection:
    name = _collection_name(workspace, embed_model_id)
    if name not in _collections:
        client = _get_client()
        try:
            collection = client.get_collection(name=name)
        except Exception:
            legacy_name = _legacy_collection_name(workspace)
            if (embed_model_id or _default_embed_model_id()) == _default_embed_model_id():
                try:
                    collection = client.get_collection(name=legacy_name)
                    _collections[name] = collection
                    return collection
                except Exception:
                    pass
            collection = client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
            )
        _collections[name] = collection
    return _collections[name]


def _batched(items: list, batch_size: int):
    for idx in range(0, len(items), batch_size):
        yield idx, items[idx: idx + batch_size]


def _serialise_tags(tags: list[str] | None) -> str:
    return ",".join(tags) if tags else ""


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
            import pytesseract  # noqa: F401 (used below)
            from pdf2image import convert_from_bytes
            images = convert_from_bytes(file_bytes, dpi=300)
            ocr_parts = []
            for img in images:
                ocr_text = pytesseract.image_to_string(img)
                if ocr_text.strip():
                    ocr_parts.append(ocr_text.strip())
            if ocr_parts:
                text = "\n\n".join(ocr_parts)
        except Exception as exc:
            logger.warning("OCR skipped because dependencies or binaries are unavailable: %s", exc)
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


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[str]:
    """Markdown-aware recursive chunker.

    Preserves code blocks and tables as atomic units, then splits on:
    1. Markdown headings (# ## ###)
    2. Blank lines (paragraphs)
    3. Sentence boundaries
    4. Words (last resort)
    """
    chunk_size = chunk_size or _retrieval_setting("chunk_size", 500)
    overlap = overlap or _retrieval_setting("chunk_overlap", 50)
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
    ingest_job_id: int | None = None,
) -> int:
    """Embed chunks and write to ChromaDB + SQLite. Returns source_id."""
    active_model_id = embed_model_id or _default_embed_model_id()
    model = _get_model(active_model_id)
    collection = _get_collection(workspace, active_model_id)
    batch_size = max(1, int(_ingestion_setting("embedding_batch_size", 64)))

    source_id = db.log_source(
        title=title, source_type=source_type, url=url,
        chunk_count=len(chunks), tags=tags,
        workspace=workspace or config.workspaces().get("default", "default"),
        embedding_model=active_model_id,
        ingest_job_id=ingest_job_id,
    )
    added_ids: list[str] = []
    tag_str = _serialise_tags(tags)

    try:
        for start_idx, batch_chunks in _batched(chunks, batch_size):
            batch_embeddings = model.encode(batch_chunks, show_progress_bar=False).tolist()
            batch_ids = [
                f"{source_id}_{start_idx + offset}_{uuid.uuid4().hex[:8]}"
                for offset in range(len(batch_chunks))
            ]
            batch_metadatas = [
                {
                    "source_id": source_id,
                    "title": title,
                    "url": url or "",
                    "chunk_index": start_idx + offset,
                    "tags": tag_str,
                }
                for offset in range(len(batch_chunks))
            ]

            collection.add(
                documents=batch_chunks,
                embeddings=batch_embeddings,
                ids=batch_ids,
                metadatas=batch_metadatas,
            )
            added_ids.extend(batch_ids)
            db.log_chunks(source_id, batch_ids, batch_chunks)
    except Exception:
        if added_ids:
            collection.delete(ids=added_ids)
        db.delete_source(source_id)
        raise

    logger.info(
        "Stored source '%s' as %s chunks in workspace=%s model=%s",
        title,
        len(chunks),
        workspace or config.workspaces().get("default", "default"),
        active_model_id,
    )
    return source_id


def _ensure_chunk_limit(title: str, chunks: list[str]) -> None:
    max_chunks = int(_ingestion_setting("max_source_chunks", 2000))
    if len(chunks) > max_chunks:
        raise ValueError(
            f'"{title}" expands to {len(chunks)} chunks, which exceeds the configured limit of '
            f"{max_chunks}. Split the document or increase ingestion.max_source_chunks."
        )


def ingest_text(
    text: str,
    title: str,
    source_type: str = "text",
    url: str | None = None,
    tags: list[str] | None = None,
    workspace: str | None = None,
    embed_model_id: str | None = None,
    ingest_job_id: int | None = None,
) -> int:
    """Chunk, embed and store raw text. Returns chunk count."""
    chunks = chunk_text(text)
    if not chunks:
        return 0
    _ensure_chunk_limit(title, chunks)
    _embed_and_store(chunks, title, source_type, url, tags, workspace, embed_model_id, ingest_job_id)
    return len(chunks)


def ingest_url(
    url: str,
    title: str | None = None,
    tags: list[str] | None = None,
    workspace: str | None = None,
    embed_model_id: str | None = None,
    ingest_job_id: int | None = None,
) -> tuple[int, bool]:
    """Fetch a URL, extract text and ingest it. Returns (chunk_count, js_warning)."""
    text, js_warning = fetch_url_text(url)
    chunk_count = ingest_text(text, title=title or url, source_type="url", url=url, tags=tags,
                              workspace=workspace, embed_model_id=embed_model_id,
                              ingest_job_id=ingest_job_id)
    return chunk_count, js_warning


def ingest_pdf(
    file_bytes: bytes,
    title: str,
    tags: list[str] | None = None,
    workspace: str | None = None,
    embed_model_id: str | None = None,
    ocr: bool = False,
    ingest_job_id: int | None = None,
) -> int:
    """Extract text from a PDF and ingest it. Returns chunk count."""
    text = extract_pdf_text(file_bytes, ocr=ocr)
    return ingest_text(text, title=title, source_type="pdf", tags=tags,
                       workspace=workspace, embed_model_id=embed_model_id,
                       ingest_job_id=ingest_job_id)


def ingest_docx(
    file_bytes: bytes,
    title: str,
    tags: list[str] | None = None,
    workspace: str | None = None,
    embed_model_id: str | None = None,
    ingest_job_id: int | None = None,
) -> int:
    """Extract text from a DOCX and ingest it. Returns chunk count."""
    text = extract_docx_text(file_bytes)
    return ingest_text(text, title=title, source_type="docx", tags=tags,
                       workspace=workspace, embed_model_id=embed_model_id,
                       ingest_job_id=ingest_job_id)


def extract_file_text(
    file_bytes: bytes,
    filename: str,
    *,
    ocr: bool = False,
) -> tuple[str, str]:
    """Extract text from a supported file and return (text, source_type)."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "pdf":
        return extract_pdf_text(file_bytes, ocr=ocr), "pdf"
    if ext == "docx":
        return extract_docx_text(file_bytes), "docx"
    return file_bytes.decode("utf-8", errors="replace"), "file"


def ingest_file(
    file_bytes: bytes,
    filename: str,
    title: str,
    tags: list[str] | None = None,
    workspace: str | None = None,
    embed_model_id: str | None = None,
    ocr: bool = False,
    ingest_job_id: int | None = None,
) -> int:
    """Ingest a file based on its extension. Returns chunk count."""
    text, source_type = extract_file_text(file_bytes, filename, ocr=ocr)
    return ingest_text(text, title=title, source_type=source_type, tags=tags,
                       workspace=workspace, embed_model_id=embed_model_id,
                       ingest_job_id=ingest_job_id)


def ingest_youtube(
    url: str,
    title: str | None = None,
    tags: list[str] | None = None,
    workspace: str | None = None,
    embed_model_id: str | None = None,
    ingest_job_id: int | None = None,
) -> int:
    """Fetch a YouTube transcript and ingest it. Returns chunk count."""
    text = fetch_youtube_transcript(url)
    return ingest_text(text, title=title or url, source_type="youtube", url=url, tags=tags,
                       workspace=workspace, embed_model_id=embed_model_id,
                       ingest_job_id=ingest_job_id)


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
    source = db.get_source(source_id)
    if source is None:
        return
    collection = _get_collection(
        source.get("workspace") or workspace,
        source.get("embedding_model"),
    )
    chroma_ids = db.get_chroma_ids_for_source(source_id)
    if chroma_ids:
        collection.delete(ids=chroma_ids)
    db.delete_source(source_id)


def update_source_tags(source_id: int, tags: list[str]) -> None:
    """Update a source's tags in both SQLite and Chroma metadata."""
    source = db.get_source(source_id)
    if source is None:
        raise ValueError(f"Source {source_id} not found")

    chunk_rows = db.get_chunks_for_source(source_id)
    if chunk_rows:
        collection = _get_collection(source.get("workspace"), source.get("embedding_model"))
        tag_str = _serialise_tags(tags)
        collection.update(
            ids=[row["chroma_id"] for row in chunk_rows],
            metadatas=[
                {
                    "source_id": source_id,
                    "title": source["title"],
                    "url": source.get("url") or "",
                    "chunk_index": row["chunk_index"],
                    "tags": tag_str,
                }
                for row in chunk_rows
            ],
        )

    db.update_source_tags(source_id, tags)


def update_chunk_text(chunk_id: int, new_text: str) -> None:
    """Update a chunk in SQLite and re-embed it in Chroma."""
    chunk = db.get_chunk(chunk_id)
    if chunk is None:
        raise ValueError(f"Chunk {chunk_id} not found")

    source = db.get_source(chunk["source_id"])
    if source is None:
        raise ValueError(f"Source {chunk['source_id']} not found")

    model_id = source.get("embedding_model") or _default_embed_model_id()
    collection = _get_collection(source.get("workspace"), model_id)
    embedding = _get_model(model_id).encode([new_text], show_progress_bar=False).tolist()[0]

    collection.update(
        ids=[chunk["chroma_id"]],
        documents=[new_text],
        embeddings=[embedding],
        metadatas=[{
            "source_id": source["id"],
            "title": source["title"],
            "url": source.get("url") or "",
            "chunk_index": chunk["chunk_index"],
            "tags": _serialise_tags(source.get("tags")),
        }],
    )
    db.update_chunk_text(chunk_id, new_text)


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
            "embedding_model": src.get("embedding_model") or _default_embed_model_id(),
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
            embed_model_id=src.get("embedding_model"),
        )
        imported += 1

    return {"imported": imported, "skipped": skipped}


def find_duplicate_chunks(threshold: float | None = None, workspace: str | None = None) -> list[dict]:
    """Find near-duplicate chunks using cosine similarity. Returns pairs above threshold."""
    if threshold is None:
        threshold = config.retrieval().get("dedup_threshold", 0.95)
    duplicates = []
    embed_models = db.get_embedding_models(workspace=workspace)
    if not embed_models:
        embed_models = [_default_embed_model_id()]

    for model_id in embed_models:
        collection = _get_collection(workspace, model_id)
        total = collection.count()
        if total < 2:
            continue

        limit = min(total, 500)
        all_data = collection.get(limit=limit, include=["documents", "metadatas", "embeddings"])
        if not all_data["embeddings"]:
            continue

        import numpy as np

        embeddings = np.array(all_data["embeddings"])
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1
        normed = embeddings / norms
        sim_matrix = normed @ normed.T

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
                            "embedding_model": model_id,
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

    try:
        count, _ = ingest_url(
            src["url"],
            title=src["title"],
            tags=src.get("tags"),
            workspace=workspace,
            embed_model_id=src.get("embedding_model"),
        )
        delete_source(source_id, workspace=workspace)
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

    source = db.get_source(source_id)
    if not source:
        return 0

    old_model_id = source.get("embedding_model") or _default_embed_model_id()
    target_model_id = embed_model_id or old_model_id
    active_workspace = workspace or source.get("workspace")
    old_collection = _get_collection(active_workspace, old_model_id)
    new_collection = _get_collection(active_workspace, target_model_id)
    old_ids = [r["chroma_id"] for r in chunks_rows]

    texts = [r["text"] for r in chunks_rows]
    model = _get_model(target_model_id)
    batch_size = max(1, int(_ingestion_setting("embedding_batch_size", 64)))
    tag_str = _serialise_tags(source.get("tags"))
    new_ids: list[str] = []

    try:
        for start_idx, batch_texts in _batched(texts, batch_size):
            batch_embeddings = model.encode(batch_texts, show_progress_bar=False).tolist()
            batch_ids = [
                f"{source_id}_{start_idx + offset}_{uuid.uuid4().hex[:8]}"
                for offset in range(len(batch_texts))
            ]
            new_collection.add(
                documents=batch_texts,
                embeddings=batch_embeddings,
                ids=batch_ids,
                metadatas=[
                    {
                        "source_id": source_id,
                        "title": source["title"],
                        "url": source.get("url") or "",
                        "chunk_index": start_idx + offset,
                        "tags": tag_str,
                    }
                    for offset in range(len(batch_texts))
                ],
            )
            new_ids.extend(batch_ids)
    except Exception:
        if new_ids:
            new_collection.delete(ids=new_ids)
        raise

    old_collection.delete(ids=old_ids)

    # Update stored chroma IDs in SQLite
    conn_rows = db.get_chunks_for_source(source_id)
    import sqlite3
    conn = sqlite3.connect(str(db.DB_PATH))
    for old_row, new_id in zip(conn_rows, new_ids):
        conn.execute("UPDATE chunks SET chroma_id = ? WHERE id = ?", (new_id, old_row["id"]))
    conn.commit()
    conn.close()
    db.update_source_embedding_model(source_id, target_model_id)

    return len(texts)
