# SecondBrain

SecondBrain is a personal knowledge base that lets you store anything you read or find useful — articles, notes, PDFs, web pages, YouTube videos, RSS feeds — and then ask questions about all of it in plain English. Instead of digging through bookmarks or searching your notes app, you just ask "What did I save about distributed systems?" and get a real answer, pulled directly from your own content, with citations pointing back to the original sources.

It runs locally on your machine. Your data stays on your disk. The only external service it talks to is Anthropic's Claude API, which generates the final answers.

---

## What problem does this solve?

Most people accumulate knowledge across dozens of places — browser bookmarks, PDFs in a downloads folder, highlights in a read-later app, notes scattered across tools. When you actually need to recall something, you're stuck trying to remember which article it was in, or scrolling through pages of results that don't quite match what you're looking for.

SecondBrain solves this by giving you a single place to dump everything, and then making all of it searchable by meaning rather than just keywords. You don't need to remember the exact words — you describe what you're looking for, and the system finds the right content even if the phrasing is completely different.

---

## How it works

The system is built on a pattern called RAG (Retrieval-Augmented Generation). Here's what actually happens under the hood:

### When you add content

1. You paste in some text, give it a URL, upload a PDF, or point it at a YouTube video
2. The text gets broken into small chunks — roughly paragraph-sized pieces of about 500 tokens each. The chunking is markdown-aware, so code blocks and tables are never split in half
3. Each chunk gets converted into a list of 384 numbers (a "vector embedding") using a small neural network that runs locally on your CPU. These numbers represent the meaning of that chunk — similar ideas produce similar numbers
4. The chunks and their embeddings are stored in ChromaDB (a vector database) on your disk, and the metadata goes into a SQLite database alongside it

### When you ask a question

1. Your question gets converted into the same kind of embedding vector
2. The system searches for stored chunks whose vectors are closest to your question vector — this is the "semantic search" part, and it works even when you use completely different words than the original text
3. At the same time, a keyword search (BM25) runs over the same chunks, catching exact term matches that the semantic search might miss
4. Both result lists get merged using Reciprocal Rank Fusion — chunks that score highly on both searches bubble to the top
5. Optionally, a second neural network (a cross-encoder) re-scores the top candidates for even more precision
6. The best 5 chunks get sent to Claude along with your question
7. Claude writes an answer using only the content from those chunks, citing which source each piece of information came from

The whole process takes a few seconds. The answer appears in a chat interface, and you can ask follow-up questions that build on the conversation.

---

## What it looks like in practice

### Example: researching a topic

Say you've been reading about system reliability over the past few weeks. You ingested a couple of AWS whitepapers, a blog post about chaos engineering, and a PDF of the Google SRE book's chapter on SLOs.

You open SecondBrain and type: *"What are the main approaches to measuring service reliability?"*

The system finds the relevant chunks across all four sources, sends them to Claude, and you get back something like:

> There are several complementary approaches to measuring service reliability:
>
> - **Service Level Indicators (SLIs)** are quantitative measures of service behavior — typically latency, error rate, and throughput [Google SRE Book]. These form the foundation of reliability measurement.
> - **Service Level Objectives (SLOs)** set target values for SLIs, such as "99.9% of requests complete in under 200ms" [Google SRE Book, AWS Well-Architected].
> - **Error budgets** quantify how much unreliability is acceptable in a given period, creating a shared framework between development velocity and operational stability [Google SRE Book].
> - **Game days and chaos engineering** validate reliability assumptions by deliberately injecting failures [Chaos Engineering Blog].

Each source is expandable — you can see the exact text chunk that was used, its relevance score, and a link back to the original URL.

### Example: quick lookups

You ingested your company's onboarding docs last month. A new team member asks you how to set up their dev environment. Instead of finding the doc, you just type: *"How do I set up the local development environment?"*

You get the answer in seconds, copy it into Slack, done.

### Example: studying

You're preparing for a certification exam. You've ingested study guides, practice question explanations, and lecture transcripts. You can quiz yourself: *"Explain the difference between eventual and strong consistency"* and get an answer drawn from multiple sources you've already studied.

---

## Common use cases

- **Research** — Ingest papers, articles, and documentation on a topic, then query across all of them at once
- **Work knowledge base** — Store internal docs, runbooks, architecture decisions, and meeting notes. Query them instead of searching Confluence
- **Study aid** — Ingest textbooks, lecture notes, and study guides. Ask questions and get answers that reference the specific material
- **Content curation** — Subscribe to RSS feeds from blogs you follow. New posts get automatically ingested and become searchable
- **Personal reference** — Save interesting articles, recipes, how-to guides, anything you might want to find again later
- **Due diligence** — Ingest a batch of documents (contracts, reports, filings) and ask specific questions across all of them

The workspace feature lets you keep these separate — a "work" workspace for professional docs, a "research" workspace for academic papers, and so on.

---

## Features

### Ingestion
- **Text** — Paste anything and give it a title
- **URLs** — Fetches and extracts the main content from web pages (detects and warns about JavaScript-rendered pages that return minimal text)
- **Files** — PDF, DOCX, TXT, Markdown, CSV, JSON, RST. PDFs with scanned images can use OCR via Tesseract
- **YouTube** — Pulls the auto-generated or community transcript, no audio processing needed
- **Bulk URLs** — Paste a list and ingest them all with a progress bar
- **RSS feeds** — Subscribe to a feed URL and fetch new entries on demand. Each entry's full article text gets ingested
- **Auto-tagging** — Toggle AI-powered tagging and Claude will suggest 3-5 tags based on the content
- **Embedding model choice** — Pick from MiniLM-L6 (default), MiniLM-L12, BGE-small, or E5-small depending on your quality/speed preference
- **Import/export** — Back up your entire knowledge base as JSON and restore it elsewhere

### Querying
- **Hybrid search** — Semantic (meaning-based) and keyword (BM25) search merged via Reciprocal Rank Fusion
- **Reranking** — Optional cross-encoder second pass for higher precision (uses ~85MB extra RAM)
- **Tag filtering** — Scope your search to specific tags
- **Similarity threshold** — Set a minimum relevance score to filter out weak matches
- **Streaming** — Answers appear token by token as Claude generates them
- **Multi-turn conversation** — Ask follow-up questions that build on previous answers in the same session
- **Model choice** — Switch between Claude Sonnet 4 (more capable) and Haiku 4.5 (faster and cheaper) per query
- **Enter to submit** — Just press Enter to ask, no need to click a button

### Managing your knowledge base
- **Source browser** — See everything you've ingested with chunk counts, types, dates, and tags
- **Inline chunk editor** — View and modify individual chunks if the extraction wasn't perfect
- **Tag editing** — Change tags on any source at any time
- **AI summarisation** — Generate a bullet-point summary of any source with one click
- **Freshness checking** — Detect when a URL's content has changed since you last ingested it
- **Re-crawl** — Re-fetch and re-ingest URLs that have changed
- **Re-embed** — Re-process all chunks with a different embedding model
- **Delete** — Clean removal from both ChromaDB and SQLite

### Workspaces
Workspaces give you separate knowledge bases within the same app. Each workspace has its own ChromaDB collection, so content in "work" doesn't mix with content in "personal." You can define workspaces in the config file or create them on the fly from the sidebar.

### Analytics and cost tracking
- **Search history** — Every query is logged with its answer. Browse past searches and re-ask them
- **Dashboard** — Source count, chunk count, query count, type breakdown, tag frequency
- **API cost tracking** — Every Claude API call is logged with token counts and estimated USD cost, broken down by model and operation (query, auto-tag, summarise, evaluation)
- **Duplicate detection** — Scan for near-duplicate chunks that might be wasting space or skewing results

### Evaluation framework
If you want to measure how well the retrieval pipeline is performing, you can define expected question-answer pairs and run automated evaluations. Claude scores each pair from 1-5, comparing the actual retrieved answer against what you expected. You get aggregate stats (average, min, max, distribution) and per-pair detail with reasoning.

This is useful when you're tuning retrieval parameters, switching embedding models, or just want confidence that the system is finding the right content.

### REST API
Everything available in the UI is also available programmatically through a FastAPI server:

```
POST /ask              — Ask a question
POST /ingest/text      — Ingest raw text
POST /ingest/url       — Fetch and ingest a URL
POST /suggest-tags     — Get AI tag suggestions for content
GET  /sources          — List all ingested sources
DELETE /sources/{id}   — Delete a source
GET  /stats            — Knowledge base statistics
GET  /usage            — API cost and usage breakdown
GET  /health           — Health check
```

Run with `uvicorn api:app --host 0.0.0.0 --port 8000`. Swagger docs are auto-generated at `/docs`.

### Docker
A Dockerfile and docker-compose.yml are included. The image is based on Python 3.12-slim and includes Tesseract and Poppler for OCR support. The compose file mounts `./data` for persistence and `./config.yaml` for live configuration.

```bash
docker-compose up -d
```

---

## Tech stack

Here's what's under the hood and why each piece was chosen.

**Streamlit** — The web UI. Streamlit turns a Python script into an interactive web app with zero frontend code. The entire interface — 7 tabs, forms, charts, expanders — is pure Python. The trade-off is less visual control than a React app, but for a personal tool the development speed is worth it.

**ChromaDB** — The vector database. It runs embedded inside the Python process (no separate server), stores data to disk, and uses HNSW indexing for fast approximate nearest-neighbour search. It was chosen over cloud-hosted alternatives like Pinecone because SecondBrain is meant to run locally.

**sentence-transformers** — Runs the embedding and reranking models locally on your CPU. The default embedding model (`all-MiniLM-L6-v2`) is 80MB, produces 384-dimensional vectors, and processes text at about 500 sentences per second on a laptop CPU. The optional reranking model (`ms-marco-MiniLM-L-6-v2`) is a cross-encoder trained on real search queries from Bing.

**Claude (Anthropic API)** — The only cloud dependency. Generates answers from retrieved context (Sonnet 4), suggests tags, and scores evaluation pairs (Haiku 4.5). Typical cost is $0.001-0.01 per query depending on chunk sizes and model choice.

**SQLite** — Stores all metadata: sources, chunks, tags, search history, API usage logs, RSS feed subscriptions, and evaluation pairs. Everything that isn't a vector lives here.

**BM25** — A custom implementation of the BM25 ranking algorithm for keyword search. Combined with semantic search via Reciprocal Rank Fusion, this gives better retrieval accuracy than either approach alone.

**pdfplumber** — PDF text extraction with table support. Falls back to Tesseract OCR (via pytesseract and pdf2image) for scanned documents when OCR mode is enabled.

**BeautifulSoup** — HTML parsing for URL ingestion. Strips navigation, scripts, and boilerplate to extract the main article content.

**feedparser** — RSS and Atom feed parsing for the subscription feature.

**FastAPI** — The REST API layer. Provides the same capabilities as the Streamlit UI for programmatic access and integration with other tools.

**YAML config** — A single `config.yaml` file controls all branding, UI text, theme colours, model selections, retrieval parameters, and workspace definitions. Change the app name, swap the default model, or adjust chunk sizes without touching Python.

---

## Getting started

### Prerequisites

- Python 3.11 or later
- An Anthropic API key (sign up at [console.anthropic.com](https://console.anthropic.com))

### Installation

```bash
git clone https://github.com/PhiSmi/SecondBrain.git
cd SecondBrain

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and add: ANTHROPIC_API_KEY=sk-ant-...
```

### Running locally

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`. First run will download the embedding model (~80MB), which takes a minute or so.

### Running with Docker

```bash
docker-compose up -d
```

This builds the image with all dependencies including OCR, mounts `./data` for persistence, and exposes port 8501.

### Running the API server

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

### Deploying to Streamlit Cloud

1. Push your repo to GitHub
2. Sign in at [share.streamlit.io](https://share.streamlit.io) and connect the repo
3. Set main file to `app.py`
4. Add secrets in the app settings:
   ```toml
   APP_PASSWORD = "your-password"
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```

Note: YouTube ingestion and some websites don't work from cloud IPs. Use paste text or file upload for those.

---

## Configuration

All configuration lives in `config.yaml`. Some of the things you can change:

| What | Where | Example |
|------|-------|---------|
| App name and tagline | `branding.app_name`, `branding.tagline` | `"MyBrain"`, `"Knowledge at your fingertips"` |
| Tab labels and UI text | `ui.tabs`, `ui.ingest`, `ui.ask`, etc. | Change any label, placeholder, or help text |
| Theme colours | `theme.primary_color`, `theme.gradient_start`, etc. | Any hex colour |
| Default LLM | `models.llm[].default` | Set `true` on whichever model you prefer |
| Embedding model | `models.embedding[].default` | Choose quality vs speed |
| Chunk size | `retrieval.chunk_size` | `500` (default), increase for longer context per chunk |
| Search depth | `retrieval.top_k`, `retrieval.final_k` | `10` candidates retrieved, `5` sent to Claude |
| Workspaces | `workspaces.predefined` | Add as many as you need |

See the file itself for the full reference — every option has an inline comment explaining what it does.

---

## Project structure

```
SecondBrain/
├── app.py              # Streamlit UI — 7 tabs (Ingest, Ask, History, Sources, RSS, Analytics, Eval)
├── api.py              # FastAPI REST API
├── query.py            # Search pipeline — hybrid retrieval, reranking, Claude generation, auto-tagging, cost tracking
├── ingest.py           # Content pipeline — extraction, markdown-aware chunking, embedding, OCR, RSS, import/export
├── db.py               # SQLite layer — sources, chunks, tags, history, API usage, feeds, eval pairs
├── evaluate.py         # Evaluation framework — automated Q&A scoring
├── config.py           # YAML config loader
├── config.yaml         # All settings in one file
├── requirements.txt    # Python dependencies
├── Dockerfile          # Container build with OCR deps
├── docker-compose.yml  # One-command deployment
├── tests/              # 48 unit tests
├── .github/workflows/  # CI pipeline (lint + test on Python 3.11/3.12/3.13)
└── data/               # Local storage — ChromaDB vectors + SQLite metadata (git-ignored)
```

---

## CI

GitHub Actions runs on every push and PR:

- Lints with ruff
- Verifies all module imports succeed
- Runs 48 unit tests covering chunking logic, BM25 scoring, Reciprocal Rank Fusion, SQLite operations, and config loading
- Tests against Python 3.11, 3.12, and 3.13

---

## Known limitations

- **JavaScript-rendered pages** — BeautifulSoup only sees static HTML. Single-page apps and some news sites return very little text. The app detects this and suggests using paste text instead
- **Cloud IP blocking** — YouTube, Reddit, and some paywalled sites reject requests from cloud provider IPs
- **RAM on free tier** — Streamlit Cloud gives you 1GB. The reranking model adds ~85MB, so it's off by default. Enable it when running locally
- **Not a production auth system** — The password gate is a simple check, not session-based authentication
- **Session-scoped chat** — Conversation context resets when you refresh. Search history is persisted separately in SQLite

---

## License

MIT
