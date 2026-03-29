# SecondBrain

A privacy-first personal knowledge base powered by RAG (Retrieval-Augmented Generation). Ingest text, URLs, PDFs, YouTube transcripts, and RSS feeds — then query everything in natural language with AI-generated answers grounded in your own content, complete with source citations.

---

## Overview

SecondBrain turns scattered notes, articles, and documents into a searchable, queryable knowledge base. It ingests content from multiple sources, breaks it into chunks, embeds each chunk as a vector, and stores everything locally. When a question is asked, it retrieves the most relevant chunks using hybrid search, then sends them to Claude to generate an answer that cites the original sources.

All data stays local. The only external call is to the Anthropic API for answer generation.

### How it works

1. **Ingest** — Content is extracted, chunked with markdown-aware splitting, embedded, and stored in ChromaDB (vectors) and SQLite (metadata)
2. **Retrieve** — Questions are embedded and matched against stored chunks using hybrid search (semantic + BM25 keyword), optionally reranked with a cross-encoder
3. **Generate** — The most relevant chunks are sent to Claude as context, producing a grounded answer with citations

---

## Features

### Content ingestion
- Paste text, URLs, PDFs, DOCX, Markdown, CSV, JSON, RST, YouTube transcripts, and bulk URL lists
- RSS/Atom feed subscriptions with automatic ingestion of new entries
- OCR fallback for scanned PDFs (via Tesseract)
- AI-powered auto-tagging using Claude
- Choice of embedding models (MiniLM-L6, MiniLM-L12, BGE-small, E5-small)
- Knowledge base import/export as JSON

### Search and retrieval
- Hybrid search combining semantic embeddings and BM25 keyword scoring via Reciprocal Rank Fusion
- Optional cross-encoder reranking for higher precision
- Tag-scoped queries, adjustable similarity threshold
- Streaming responses with multi-turn conversation support
- Choice of LLM (Claude Sonnet 4 or Haiku 4.5)
- Press Enter to submit questions

### Source management
- Inline chunk viewing and editing
- Tag editing, AI summarisation, URL freshness detection
- Re-crawl changed URLs, re-embed with different models
- Delete sources with full cleanup across both databases

### Workspaces
- Separate knowledge bases per project (work, research, personal, etc.)
- Pre-defined or user-created workspaces with sidebar switching

### Analytics and evaluation
- Search history with re-ask capability
- Dashboard with source/chunk/query counts, type breakdowns, tag frequency
- Per-call API cost tracking broken down by model and operation
- Near-duplicate chunk detection
- Evaluation framework: define expected Q&A pairs, run automated scoring (1-5) via Claude, view distribution and per-pair reasoning

### REST API
A FastAPI wrapper provides programmatic access to the full pipeline:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ask` | POST | Ask a question |
| `/ingest/text` | POST | Ingest raw text |
| `/ingest/url` | POST | Fetch and ingest a URL |
| `/suggest-tags` | POST | Get AI tag suggestions |
| `/sources` | GET | List all sources |
| `/sources/{id}` | DELETE | Delete a source |
| `/stats` | GET | Knowledge base statistics |
| `/usage` | GET | API cost and usage stats |
| `/health` | GET | Health check |

### Docker support
Ship as a single container with all dependencies (including OCR). A `docker-compose.yml` is provided for one-command deployment with persistent storage.

---

## Tech stack

| Component | Technology | Role |
|-----------|-----------|------|
| UI | Streamlit | 7-tab web interface with custom theming |
| Vector DB | ChromaDB | Local embedding storage and similarity search |
| Embeddings | sentence-transformers (MiniLM) | Text-to-vector conversion, runs on CPU |
| Reranking | Cross-encoder (ms-marco-MiniLM) | Optional precision reranking |
| Keyword search | BM25 (custom) | Statistical keyword scoring for hybrid search |
| LLM | Claude (Anthropic API) | Answer generation and auto-tagging |
| Metadata | SQLite | Sources, chunks, tags, history, usage, feeds, eval pairs |
| PDF | pdfplumber + pytesseract | Text extraction with OCR fallback |
| Web | BeautifulSoup + requests | URL content extraction |
| RSS | feedparser | Feed parsing and entry tracking |
| REST API | FastAPI + uvicorn | Programmatic access |
| Config | YAML | All branding, models, and defaults in one file |
| CI | GitHub Actions | Lint + test on Python 3.11/3.12/3.13 |

---

## Getting started

### Prerequisites

- Python 3.11+
- An Anthropic API key from [console.anthropic.com](https://console.anthropic.com)

### Install and run

```bash
git clone https://github.com/PhiSmi/SecondBrain.git
cd SecondBrain
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env

streamlit run app.py
```

Opens at `http://localhost:8501`.

### Docker

```bash
docker-compose up -d
```

Or manually:

```bash
docker build -t secondbrain .
docker run -p 8501:8501 --env-file .env -v ./data:/app/data secondbrain
```

### FastAPI server

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

Swagger docs at `http://localhost:8000/docs`.

### Streamlit Cloud

1. Push to GitHub
2. Connect at [share.streamlit.io](https://share.streamlit.io)
3. Set main file to `app.py`
4. Add secrets:
   ```toml
   APP_PASSWORD = "your-password"
   ANTHROPIC_API_KEY = "your-key"
   ```

Note: YouTube and some sites block cloud IPs. Use paste or file upload for those.

---

## Configuration

Everything is configured through **`config.yaml`** — branding, UI text, theme colours, models, retrieval parameters, and workspaces. No Python changes needed.

### Key sections

**Branding** — app name, emoji, tagline, browser tab title

**Models** — LLM and embedding model options with defaults

**Retrieval** — chunk size (500), overlap (50), top-k (10), final-k (5), RRF constant (60), similarity threshold, dedup threshold

**Theme** — colour palette, gradients, fonts (applied via CSS)

**Workspaces** — enable/disable, default workspace, pre-defined workspace list

See `config.yaml` for the full reference with inline comments.

---

## Project structure

```
SecondBrain/
├── app.py              # Streamlit UI (7 tabs)
├── api.py              # FastAPI REST wrapper
├── config.py           # YAML config loader
├── config.yaml         # All settings and customisation
├── evaluate.py         # Q&A evaluation framework
├── ingest.py           # Content extraction, chunking, embedding, RSS, OCR
├── query.py            # Hybrid search, reranking, generation, auto-tagging, cost tracking
├── db.py               # SQLite schema and queries
├── requirements.txt    # Dependencies
├── Dockerfile          # Container with OCR deps
├── docker-compose.yml  # One-command deployment
├── tests/              # 48 unit tests
├── .github/workflows/  # CI pipeline
├── .streamlit/         # Streamlit config and secrets
└── data/               # ChromaDB + SQLite (git-ignored)
```

---

## How the retrieval pipeline works

The search pipeline combines two complementary approaches:

**Semantic search** finds content by meaning. "deployment process" matches "how to release" even though they share no words. This uses embedding vectors and cosine similarity via ChromaDB.

**BM25 keyword search** finds content by exact terms. "Kubernetes" always matches documents containing "Kubernetes". This is a statistical scoring algorithm that weights term frequency and document rarity.

**Reciprocal Rank Fusion** merges both ranked lists into one. A document ranked highly by both methods scores higher than one ranked by only one. The formula: `score = 1/(k + rank_semantic) + 1/(k + rank_bm25)` with k=60.

**Cross-encoder reranking** (optional) takes the merged top-10 and re-scores each one by passing the query and document together through a cross-encoder model. This is slower but more precise than the bi-encoder approach used for initial retrieval. The top 5 after reranking are sent to Claude.

Benchmarks consistently show hybrid search outperforms either approach alone by 5-15% on retrieval accuracy.

---

## Limitations

- JavaScript-rendered pages (SPAs, some news sites) return minimal content — the app detects and warns about this
- YouTube transcript ingestion works locally but not from cloud-hosted deployments
- Reranking is off by default to stay within Streamlit Cloud's 1GB RAM limit
- Password protection is a simple gate, not production-grade authentication
- Chat history is session-scoped; search history persists in SQLite

---

## License

MIT
