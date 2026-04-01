# SecondBrain

SecondBrain is a local-first knowledge base for material worth keeping.

It ingests notes, URLs, PDFs, DOCX files, YouTube transcripts, images, and RSS content, stores them locally, and lets them be queried through a retrieval-augmented workflow. Retrieval and embeddings run on the host machine. Claude is used for answer generation, summaries, auto-tagging, image analysis, and evaluation.

The project is designed for personal research libraries, work documentation, study material, and any collection of source content that is easier to ask than to browse.

## Product Overview

SecondBrain brings three things together:

- A simple ingestion surface for saved content.
- A local retrieval stack built on ChromaDB plus sentence-transformers.
- A query interface that answers from retrieved evidence instead of generic model recall.

The result is a searchable memory layer for content already collected:

- Technical notes and bookmarks
- Internal documentation and runbooks
- Research papers and study guides
- Reading lists and newsletter archives
- PDF-heavy reference material
- Screenshots, diagrams, and whiteboard photos
- Topic-specific workspaces for different domains

## What It Does

### Ingestion

- Paste raw text
- Ingest a URL
- Upload `pdf`, `docx`, `txt`, `md`, `csv`, `json`, or `rst`
- Fetch YouTube transcripts
- Upload images (Claude Vision extracts text, describes diagrams and charts)
- Ingest URLs in bulk
- Queue long-running imports in the background
- Subscribe to RSS feeds and pull new entries on demand
- Import and export the knowledge base as JSON

### Retrieval and Q&A

- Semantic search with sentence-transformers
- BM25 keyword search
- Hybrid retrieval with Reciprocal Rank Fusion
- Optional cross-encoder reranking
- HyDE (Hypothetical Document Embeddings) for better conceptual retrieval
- Query decomposition for complex multi-part questions
- Contextual compression to reduce noise in retrieved chunks
- Streaming answers
- Tag filters
- Multi-turn chat history
- AI-generated follow-up question suggestions
- Markdown export for the latest answer

### Knowledge Discovery

- Workspace digest — AI-generated summary of key themes, connections, and knowledge gaps
- Semantic source search — find sources by meaning, not just keywords
- Related sources — discover connections between sources via embedding similarity
- Knowledge coverage view — visual tag distribution

### Knowledge Base Management

- Browse ingested sources
- Search sources by title or URL
- Edit tags
- Edit chunk text
- Re-embed stored sources
- Summarise sources
- Check URL freshness
- Remove sources cleanly from both SQLite and Chroma

### Workspace and Ops

- Separate workspaces
- Persisted workspace registry so empty workspaces remain selectable
- Per-source embedding model tracking
- Background ingestion jobs with persisted status
- Standalone worker support for durable queued ingestion
- Workspace-aware history
- Workspace-aware API usage analytics
- Duplicate chunk scanning
- Manual evaluation runs against expected answers

### Analytics

- Source, chunk, and query count metrics
- Source type breakdown (bar chart)
- Tag frequency distribution (bar chart)
- Embedding model usage (bar chart)
- Ingestion timeline — sources and chunks created per day (area charts)
- API cost breakdown by model and operation

### API

The FastAPI app exposes a programmatic surface for the core workflow:

- `POST /ask` — query with optional HyDE, decomposition, and compression
- `POST /ingest/text`
- `POST /ingest/url`
- `POST /jobs/ingest/text`
- `POST /jobs/ingest/url`
- `POST /jobs/ingest/youtube`
- `POST /jobs/ingest/bulk-urls`
- `GET /jobs`
- `GET /jobs/{job_id}`
- `POST /jobs/{job_id}/cancel`
- `POST /suggest-tags`
- `POST /discover/digest` — generate workspace digest
- `GET /discover/related/{source_id}` — find related sources
- `POST /discover/search` — semantic source search
- `POST /ask/followups` — suggest follow-up questions
- `GET /workspaces`
- `POST /workspaces`
- `GET /sources`
- `DELETE /sources/{source_id}`
- `GET /stats`
- `GET /usage`
- `GET /health`

## How It Works

### Ingestion Pipeline

1. Content is extracted from the source (text, HTML, PDF, DOCX, YouTube, image via Claude Vision).
2. Text is split into chunks using a markdown-aware chunker.
3. Each chunk is embedded locally.
4. Vectors are stored in ChromaDB.
5. Source metadata, chunks, tags, usage records, history, feeds, and evaluation pairs are stored in SQLite.

### Query Pipeline

1. The question is embedded using the relevant embedding model.
2. Candidate chunks are retrieved with semantic search.
3. BM25 scores are computed over the same result set.
4. Results are fused with Reciprocal Rank Fusion.
5. Optional reranking improves the final context set.
6. Optional contextual compression extracts only the relevant parts of each chunk.
7. Claude answers strictly from the retrieved context.

### Advanced Retrieval Modes

**HyDE (Hypothetical Document Embeddings):** Instead of embedding the question directly, Claude generates a hypothetical passage that would answer the question, then that passage is embedded and used for retrieval. This often finds better results for abstract or conceptual queries because the hypothetical document is closer in embedding space to actual relevant documents.

**Query Decomposition:** Complex multi-part questions are broken into 2-4 simpler sub-questions. Each sub-question retrieves independently, and the results are merged via Reciprocal Rank Fusion. This improves recall for questions like "Compare X and Y, and explain how Z relates to both."

**Contextual Compression:** After retrieval, each chunk is passed through Claude (Haiku, for speed and cost) to extract only the sentences relevant to the question. The compressed chunks are then sent to the main model. This reduces noise significantly when chunks contain mixed-relevance content.

### Model Handling

Embedding models are tracked per source. A workspace can contain content embedded with different models, and the query path searches across the embedding-model collections present in that workspace.

That matters for long-lived libraries. It means sources can be re-embedded over time without breaking old content or making retrieval inconsistent.

## Architecture

### Core Stack

- **Streamlit** for the primary application UI
- **FastAPI** for the HTTP API
- **ChromaDB** for local vector storage
- **SQLite** for metadata, history, feeds, evaluation pairs, and usage
- **sentence-transformers** for local embeddings and reranking
- **Claude** for generation, summaries, auto-tagging, image analysis, evaluation scoring, HyDE, decomposition, compression, follow-ups, and workspace digests

### Storage Model

- `data/chroma/` stores vector collections
- `data/metadata.db` stores the relational metadata

Collections are namespaced by workspace and embedding model. Source edits update both SQLite and Chroma so the UI and retrieval layer stay aligned.

### Persistence

SecondBrain is persistent as long as the `data/` directory is retained.

- SQLite metadata lives in `data/metadata.db`
- Chroma collections live in `data/chroma/`
- queued file uploads use `data/job_uploads/`

For local use, that means keeping the repository's `data/` folder. For Docker, it means mounting `./data` into the container so restarts do not wipe the knowledge base.

## Workspaces

Workspaces are separate knowledge domains within one deployment.

Typical examples:

- `default` for general saved material
- `work` for internal documentation
- `research` for papers, notes, and literature review

Each workspace has:

- Its own source set
- Its own vector collections
- Its own search history
- Its own API usage breakdown
- Its own duplicate detection results
- Its own AI-generated digest

## Deployment Notes and Limits

SecondBrain is optimized for local or Docker-based use, but it also runs on Streamlit Cloud.

This repository ships with explicit guardrails:

- Streamlit upload limit: `15 MB`
- Maximum expanded source size: `2000` chunks
- Batched embedding writes to reduce peak memory
- Background ingestion queue for longer-running imports

Why the limits exist:

- File size on disk is not the same as extracted text size in memory
- PDFs can expand substantially during text extraction
- OCR is the most expensive ingest path
- Streamlit Cloud workers have limited memory compared to local or containerized deployments

If a document exceeds the configured limits, the app fails fast with a clear message instead of letting the worker crash.

## OCR Support

OCR is optional and intended for scanned PDFs.

The repository includes:

- Python OCR dependencies in `requirements.txt`
- System OCR dependencies for Streamlit Cloud in `packages.txt`
- System OCR dependencies in `Dockerfile`

OCR is only used when explicitly enabled in the UI. If the binaries are not available, the app falls back to the extracted text path and logs a warning.

## Running Locally

### Requirements

- Python 3.11 or later
- An Anthropic API key

### Setup

```bash
git clone https://github.com/PhiSmi/SecondBrain.git
cd SecondBrain

python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

macOS / Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add the API key to `.env`:

```env
ANTHROPIC_API_KEY=your-key-here
```

Optional:

```env
APP_PASSWORD=your-password
```

### Start the App

```bash
streamlit run app.py
```

### Start the API

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

### Run the Test Suite

```bash
pytest -q
```

## Docker

The repository includes a `Dockerfile` and `docker-compose.yml`.

```bash
docker-compose up -d
```

The compose stack runs:

- `secondbrain` for the Streamlit UI (with health check)
- `secondbrain-worker` for durable queued ingestion (with health check)

Docker is the better choice when:

- OCR needs to be available consistently
- persistent storage matters
- deployments should behave the same across machines
- larger local libraries are expected

## Streamlit Cloud

### Included Cloud Support

The repository is prepared for Streamlit Cloud:

- `requirements.txt` is pinned
- Linux installs use CPU Torch wheels
- `packages.txt` installs `tesseract-ocr` and `poppler-utils`
- `.streamlit/config.toml` sets the upload limit and theme

### Cloud Setup

1. Push the repository to GitHub.
2. Create a new Streamlit app.
3. Set `app.py` as the entry point.
4. Add secrets:

```toml
ANTHROPIC_API_KEY = "..."
APP_PASSWORD = "..." # optional
```

### Operational Expectations

- First use will download embedding model weights from Hugging Face.
- Large documents are better handled locally or via Docker.
- OCR requires both the Python and system dependencies.
- Community Cloud is suitable for moderate knowledge bases, not heavy document-processing workloads.
- Streamlit Cloud uses the embedded worker because it cannot run the separate Docker worker service.

## Configuration

All product behavior is centralized in `config.yaml`.

### Major Sections

- `branding`: app identity and browser metadata
- `ui`: labels, headings, and help text
- `theme`: colors and typography
- `models`: LLM and embedding model options
- `retrieval`: chunking, retrieval defaults, and advanced mode toggles
- `ingestion`: upload and chunk limits
- `jobs`: worker mode, poll interval, and lease duration
- `workspaces`: predefined workspaces
- `recrawl`: URL re-crawl defaults

### Important Operational Settings

| Setting | Meaning |
|---|---|
| `retrieval.chunk_size` | Target chunk size used during ingestion |
| `retrieval.chunk_overlap` | Overlap between adjacent chunks |
| `retrieval.top_k` | Retrieval breadth before reranking |
| `retrieval.final_k` | Final number of chunks sent to Claude |
| `retrieval.default_hyde` | Enable HyDE retrieval by default |
| `retrieval.default_decompose` | Enable query decomposition by default |
| `retrieval.default_compress` | Enable contextual compression by default |
| `retrieval.default_followups` | Enable follow-up suggestions by default |
| `ingestion.max_upload_mb` | Streamlit file upload limit |
| `ingestion.max_source_chunks` | Guardrail for oversized extracted sources |
| `ingestion.embedding_batch_size` | Batch size used when writing embeddings |

## Product Behavior Worth Knowing

### Source Edits

When source tags or chunk text are edited from the UI, the change is written to both SQLite and Chroma. This keeps retrieval, filters, and the source browser in sync.

### Re-embedding

Re-embedding does not blindly overwrite the only copy of the vectors. New vectors are created first, then the old vectors are removed once the replacement succeeds.

### URL Re-crawl

URL freshness checks compare the current extracted text against the stored source. If a re-crawl is triggered, the replacement ingest must succeed before the older source is removed.

### History and Usage

Search history and API usage are tracked per workspace, which keeps analytics meaningful when one deployment is used for multiple domains.

### Background Jobs

Imports can be queued into a persisted background worker instead of running inline with the Streamlit request cycle.

That means large URL batches, transcript pulls, and heavier file ingests no longer have to keep the UI blocked while retrieval storage is being updated.

Each job stores:

- progress counters and a status message
- worker heartbeat and lease data
- attempt count so stale jobs can be reclaimed after worker failure

In Docker, queued ingestion is intended to be handled by the dedicated `secondbrain-worker` service. In Streamlit-only deployments, the embedded worker remains available for convenience.

The worker loop includes crash recovery: unexpected exceptions are logged and the worker continues after a brief cooldown instead of crashing the thread.

## API Reference

### `POST /ask`

Ask a question against the active knowledge base.

Request:

```json
{
  "question": "What did I save about service reliability?",
  "tags": ["sre"],
  "hybrid": true,
  "use_rerank": false,
  "use_hyde": false,
  "use_decompose": false,
  "use_compress": false,
  "model_id": "claude-sonnet-4-20250514",
  "min_similarity": 0.0,
  "workspace": "research"
}
```

### `POST /ingest/text`

Ingest raw text.

### `POST /ingest/url`

Fetch, extract, and ingest a URL.

### `POST /jobs/ingest/text`

Queue raw text ingestion and return a job id immediately.

### `POST /jobs/ingest/url`

Queue URL ingestion and return a job id immediately.

### `POST /jobs/ingest/youtube`

Queue transcript ingestion for a YouTube URL.

### `POST /jobs/ingest/bulk-urls`

Queue a batch of URLs for ingestion.

### `GET /jobs`

List recent background ingestion jobs.

### `GET /jobs/{job_id}`

Return one background ingestion job.

### `POST /jobs/{job_id}/cancel`

Cancel a pending job immediately or request cancellation for a running job.

### `POST /suggest-tags`

Suggest tags for arbitrary text.

### `POST /discover/digest`

Generate an AI-powered digest of the workspace's themes and connections.

### `GET /discover/related/{source_id}`

Find sources semantically related to a given source.

### `POST /discover/search`

Search sources by semantic similarity to a query.

### `POST /ask/followups`

Suggest follow-up questions based on a Q&A exchange.

### `GET /workspaces`

List persisted workspaces.

### `POST /workspaces`

Create a workspace before any sources have been added to it.

### `GET /sources`

List sources for a workspace.

### `GET /stats`

Return source, chunk, and query counts plus tag and type breakdowns.

### `GET /usage`

Return API usage and cost information. Supports `workspace` as a query parameter.

### `GET /health`

Structured runtime validation for storage, API key presence, worker state, OCR availability, and persistence paths.

## Validation and Troubleshooting

The Streamlit UI includes a setup and validation panel in the Ingest tab, and the API exposes the same information through `GET /health`.

Use that surface to confirm:

- the SQLite metadata database is writable
- the Chroma directory is writable
- the background job upload directory exists
- the Anthropic API key is configured
- the embedded worker is online or intentionally disabled
- OCR support is fully available or only partially installed

## Project Structure

- `app.py` — Streamlit application (8 tabs: Ingest, Ask, History, Sources, Discover, RSS Feeds, Analytics, Eval)
- `background_jobs.py` — persisted in-process ingestion worker with crash recovery
- `api.py` — FastAPI wrapper with 22 endpoints
- `config.py` — config loader and helpers
- `config.yaml` — product configuration
- `db.py` — SQLite layer
- `ingest.py` — extraction, chunking, embedding, storage, and maintenance operations
- `query.py` — retrieval, reranking, generation, HyDE, decomposition, compression, follow-ups, digests, image analysis, and semantic source search
- `evaluate.py` — evaluation workflow with per-pair error recovery
- `worker.py` — standalone durable queue worker
- `tests/` — unit tests
- `packages.txt` — system packages for Streamlit Cloud OCR support

## Privacy and Security

Source content, embeddings, and metadata remain local to the deployment environment.

The external calls made by the application are:

- Anthropic API calls for generation, summarisation, tagging, image analysis, evaluation, HyDE, decomposition, compression, follow-ups, and digests
- Hugging Face model downloads on first use
- URL and feed fetches when ingesting web content

An application password gate is available through `APP_PASSWORD`.

## Known Tradeoffs

SecondBrain deliberately favors a compact, local-first architecture over a distributed one.

That keeps setup simple, but it also means:

- Streamlit remains the main UX layer
- Chroma runs embedded in-process
- queued ingestion is durable in Docker, but still lightweight compared with a full distributed job system
- very heavy imports are still better suited to Docker or a dedicated service host
- advanced retrieval modes (HyDE, decomposition, compression) add Claude API calls and latency in exchange for quality

For personal libraries and small-team knowledge bases, that tradeoff is usually the right one. For heavier pipelines, the natural next steps are external workers, job queues, stricter end-to-end integration tests, and a richer API surface.
