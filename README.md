# SecondBrain

A local, privacy-first knowledge base powered by RAG (Retrieval-Augmented Generation). Feed it text, URLs, PDFs, or YouTube transcripts — then ask questions in natural language and get answers grounded in your own content, with source citations.

---

## TL;DR

1. Feed it content — paste text, drop a URL, upload a PDF, or point it at a YouTube video
2. It gets chunked, embedded, and stored in a local vector database
3. Ask questions in plain English
4. Get AI-generated answers citing exactly which sources the information came from

No cloud storage. No data leaves your machine (except the query to Claude for answer generation). Everything else runs locally.

---

## What It Is and How It Works

SecondBrain is a personal knowledge management tool that turns unstructured text into a searchable, queryable knowledge base. Think of it as a personal research assistant that only knows what you've fed it.

### The 30-Second Version

You have articles, notes, and web pages scattered everywhere. You want to ask "What did I read about X?" and get a real answer — not a list of links, but an actual synthesised response pointing to the exact sources.

SecondBrain does this in two steps:

**Step 1 — You feed it content.** Paste text, give it a URL, upload a PDF, or point it at a YouTube video. Behind the scenes, the app breaks the text into small chunks, converts each chunk into a mathematical representation of its meaning (an "embedding"), and stores everything in a local database on your machine.

**Step 2 — You ask questions.** Type a question in plain English. The app converts your question into the same mathematical form, finds the stored chunks whose meaning is closest to your question, optionally reranks them for precision, sends those chunks to Claude (Anthropic's AI), and Claude writes you an answer using *only* that content — with citations back to the original sources.

This pattern is called **RAG** (Retrieval-Augmented Generation):

- **Retrieval**: Finding the most relevant chunks of your stored content using hybrid search (semantic similarity + keyword matching)
- **Augmented Generation**: Passing those chunks as context to Claude, which generates a grounded answer — not from its training data, but from *your* content

The result: you ask "What are the key reliability principles I read about?" and you get a coherent answer citing the specific articles you ingested, not a generic LLM response.

---

## Core Concepts

If you're new to any of these ideas, this section explains each building block from the ground up.

### What Is RAG (Retrieval-Augmented Generation)?

Large Language Models like Claude are trained on massive datasets, but that training data is frozen at a point in time and doesn't include your private notes, company docs, or bookmarked articles. RAG is a pattern that bridges this gap.

Instead of asking the LLM to answer from memory, RAG **retrieves** relevant content from your own data first, then passes it to the LLM as context. The LLM generates its answer based on what it was given — not what it was trained on. This means:

- **Grounded answers**: The LLM can only reference content you've actually stored, dramatically reducing hallucination
- **Up-to-date information**: You control what's in the knowledge base — ingest a new article today, ask about it today
- **Private data stays useful**: Your personal notes, internal docs, and research become queryable without ever being sent to a training pipeline

The RAG pattern has three phases:

1. **Ingest** (offline): Take your content, break it into chunks, convert each chunk into a numerical vector (an "embedding"), and store those vectors in a database
2. **Retrieve** (at query time): Convert your question into the same kind of vector, then search the database for the stored vectors most similar to your question
3. **Generate** (at query time): Pass the matching text chunks to the LLM as context, and ask it to answer your question using only that context

### What Are Embeddings?

An embedding is a list of numbers (a "vector") that represents the meaning of a piece of text. The key insight is that **semantically similar text produces geometrically close vectors**.

For example, these two sentences share almost no words, but an embedding model places them near each other in vector space:

- "How do I deploy to production?"
- "Our release process involves pushing to the main branch"

Both are about deployment/releases, and the embedding model captures that. Meanwhile, "How do I deploy to production?" and "The cat sat on the mat" would be far apart — they're about completely different things.

SecondBrain uses the `all-MiniLM-L6-v2` model, which produces 384-dimensional vectors. Each chunk of your content gets converted into a list of 384 numbers. Your question gets converted the same way. Then we just find which stored vectors are closest to the question vector — that's semantic search.

**Why not just use keyword search?** Keyword search (like Ctrl+F) only finds exact word matches. If your notes say "deployment process" but you search for "how to release", keyword search finds nothing. Semantic search finds it because the *meaning* is similar, regardless of the exact words used.

### What Is a Vector Database?

A vector database is a specialised database designed to store and search high-dimensional vectors efficiently. Traditional databases are built for exact lookups ("find the row where id = 42"). Vector databases are built for similarity lookups ("find the 5 vectors closest to this query vector").

SecondBrain uses **ChromaDB**, which:

- Runs entirely locally — no server to set up, no cloud account needed
- Stores data persistently in a folder on your disk (`data/chroma/`)
- Uses an algorithm called **HNSW** (Hierarchical Navigable Small World) for fast approximate nearest-neighbour search — it doesn't compare your query against every single stored vector; instead it navigates a graph structure to find close matches quickly
- Uses **cosine similarity** as the distance metric — this measures the angle between two vectors, where identical directions = 1.0 (perfect match) and perpendicular = 0.0 (no relationship)

**Why not just store embeddings in a regular database?** You could, but searching would require computing the distance between your query and every single stored vector — an O(n) operation that gets slow as your knowledge base grows. HNSW gives you approximate results in O(log n) time.

### What Is Chunking?

A chunk is simply a small piece of a larger document. When you ingest an article, you don't store it as one giant block of text — you slice it into smaller pieces, and each piece is a chunk.

**The problem with storing a whole document as one unit:**

Embedding models turn text into a vector that represents its meaning. If you embed an entire 5,000-word article, the vector becomes a blurry average of every topic in that article. When you ask "what are the reliability principles?", the whole-article vector might not score highly against your question — even if the answer is clearly in there somewhere.

**What chunking solves:**

Each chunk gets its own embedding — a precise vector for *that specific section's* meaning. When you ask a question, you find the 2–3 chunks most relevant to it, not the whole article.

**Concrete example** — a 3,000-word AWS article splits into roughly 6 chunks:

```
Chunk 1: Introduction + overview
Chunk 2: Reliability pillar — design principles
Chunk 3: Reliability pillar — best practices
Chunk 4: Security pillar — design principles
Chunk 5: Security pillar — best practices
Chunk 6: Summary
```

You ask: *"What are the reliability best practices?"*

- Chunks 2 and 3 score ~0.85 similarity — sent to Claude
- Chunks 4 and 5 score ~0.30 (security, not reliability) — ignored

Only the relevant chunks reach Claude, keeping the answer focused and the API cost low.

SecondBrain uses a **recursive chunking** strategy:

1. **Split on headings first** (Markdown `#`, `##`, etc.) — respects the author's own document structure
2. **Split by paragraphs** if a headed section is too long
3. **Split by sentences** if a paragraph still exceeds the chunk size
4. **Split by words** as a last resort
5. **Overlap between chunks** (~50 tokens) — if a key sentence falls right on the boundary between chunk 2 and chunk 3, it appears in both, so it's never lost

**Why ~500 tokens?** It's a sweet spot. Too small (50 tokens) and you lose context — the chunk might be a single sentence ripped from its paragraph. Too large (2,000 tokens) and the embedding becomes a blurry average of too many ideas, making retrieval less precise. 500 tokens is roughly a solid paragraph or two — enough context to be meaningful, focused enough to embed well.

### What Is an LLM (Large Language Model)?

An LLM is a neural network trained on vast amounts of text that can generate human-like responses. In SecondBrain, Claude (by Anthropic) serves as the answer generator. It doesn't search your knowledge base — it receives the already-retrieved chunks as context and synthesises them into a coherent answer.

The system prompt constrains Claude to:
- Only answer from the provided context (not its general training knowledge)
- Cite which source each piece of information came from
- Admit when the context doesn't contain enough information to answer

This constraint is what makes RAG reliable. Without it, the LLM might confidently make things up. With it, you get traceable, source-backed answers.

### What Is Cosine Similarity?

When comparing two vectors, cosine similarity measures the cosine of the angle between them. It ranges from -1 to 1:

- **1.0** — vectors point in the same direction (identical meaning)
- **0.0** — vectors are perpendicular (unrelated meaning)
- **-1.0** — vectors point in opposite directions (opposite meaning)

In practice, most text embeddings fall between 0.3 and 0.9. A score of 0.75+ usually indicates strong relevance. SecondBrain returns the top chunks by similarity and shows you the score so you can judge how relevant each source is.

Cosine similarity is preferred over Euclidean distance for text because it's **magnitude-invariant** — it cares about the direction of the vector (what the text means), not its length (how long the text is).

### What Is a System Prompt?

When you call an LLM API, you can provide a "system prompt" — instructions that shape how the model behaves for the entire conversation. It's like giving the model a job description before it starts answering.

SecondBrain's system prompt tells Claude:
> "You are a helpful research assistant. Answer based ONLY on the provided context. Cite your sources. If the context doesn't have the answer, say so."

This is critical for RAG. Without this constraint, the model might blend its training knowledge with the retrieved context, making it impossible to trace where an answer came from.

---

## The Tech Stack — In Depth

This section goes deeper into every technology SecondBrain uses, what it does, and why it was chosen.

### sentence-transformers and SBERT

The `sentence-transformers` Python package is the framework that runs the embedding model. It was built by the team behind **SBERT** (Sentence-BERT), a 2019 research project that adapted BERT (Google's language model) for producing sentence-level embeddings efficiently.

**The history:** BERT (2018) was revolutionary for understanding language, but it wasn't designed to compare sentences. Comparing two sentences with BERT required passing them *together* through the model — an O(n²) problem if you wanted to compare one query against thousands of documents. SBERT solved this by fine-tuning BERT with a **siamese network** architecture: each sentence goes through the model independently, producing a fixed-size vector. Comparing those vectors is just a dot product — effectively instant.

**What `sentence-transformers` gives us:**
- A simple Python API: `model.encode(["some text"])` → returns a numpy array of 384 floats
- Automatic model downloading from Hugging Face Hub (first run downloads, subsequent runs use cache)
- CPU inference out of the box — no GPU driver setup required
- Access to hundreds of pre-trained models for different tasks (semantic search, paraphrase detection, clustering)

**This is not an LLM.** The embedding model doesn't generate text, hold conversations, or "understand" anything in the way Claude does. It's a much smaller neural network (~22M parameters vs Claude's hundreds of billions) with exactly one job: convert a piece of text into a list of numbers that represents its meaning.

### all-MiniLM-L6-v2 — The Embedding Model

This is the specific model SecondBrain uses for creating embeddings. The name encodes its architecture:

- **MiniLM** — a distilled (compressed) version of a larger language model. Microsoft's MiniLM technique takes a large teacher model and trains a smaller student model to mimic it, retaining most of the quality at a fraction of the size
- **L6** — 6 transformer layers (vs 12 in BERT-base). Fewer layers = faster inference, smaller RAM footprint
- **v2** — second generation, trained on over 1 billion sentence pairs from diverse sources

**Key specs:**
| Property | Value |
|----------|-------|
| Parameters | ~22 million |
| Output dimensions | 384 |
| Model size | ~80MB |
| Max input length | 256 tokens (~200 words) |
| Speed | ~14,000 sentences/second on GPU, ~500/second on CPU |
| Training data | 1B+ sentence pairs from NLI, paraphrase, Q&A, and web data |

**What those 384 dimensions represent:** Each dimension captures some aspect of meaning — but not in a way humans can interpret individually. Dimension 47 isn't "how much this text is about dogs." Instead, the 384 numbers work together as a holistic representation. Two texts about similar topics will have similar values across most dimensions, resulting in high cosine similarity. The model learned these representations from billions of examples of text pairs that mean similar or different things.

**Why this model and not something bigger?** For a personal knowledge base with hundreds to thousands of chunks, MiniLM is more than sufficient. Larger models like `bge-large-en-v1.5` (1024 dimensions, ~335M parameters) give ~2-3% better retrieval accuracy on benchmarks, but use 4x more RAM and are 4x slower. The accuracy difference is negligible at this scale. You'd switch to a larger model when doing production search over millions of documents.

### Cross-Encoder Reranking (ms-marco-MiniLM-L-6-v2)

SecondBrain has an optional second model — a **cross-encoder** used for reranking search results. This is fundamentally different from the embedding model:

**Bi-encoder (embedding model) — fast but approximate:**
```
"reliability principles"  →  [0.12, -0.34, ...]  ─┐
                                                     ├→ cosine similarity → 0.82
"design for reliability"  →  [0.15, -0.31, ...]  ─┘
```
Each text is encoded independently. Fast — you encode the query once and compare against all stored vectors. But the model never sees both texts together, so it can miss nuanced relationships.

**Cross-encoder — slow but precise:**
```
["reliability principles", "design for reliability"]  →  model  →  0.94
```
Both texts go through the model *together*. The model can attend to specific word interactions between the query and the document. Much more accurate, but O(n) — you have to run it for every query-document pair.

**How SecondBrain combines them:**
1. The bi-encoder retrieves the top 10 candidates quickly (milliseconds)
2. The cross-encoder reranks those 10 candidates precisely (a few seconds)
3. The top 5 after reranking are sent to Claude

This is called a **retrieve-then-rerank** pattern. You get the speed of bi-encoder search with the precision of cross-encoder scoring.

The cross-encoder model (`ms-marco-MiniLM-L-6-v2`) was trained on the MS MARCO dataset — millions of real Bing search queries paired with relevant/irrelevant passages. It learned what makes a passage a good answer to a query.

**Why it's off by default:** The reranker adds ~85MB of RAM. On Streamlit Cloud's free tier (1GB), this can cause out-of-memory crashes. Locally, you can turn it on for better precision.

### Hybrid Search: Semantic + BM25

SecondBrain doesn't rely on embeddings alone. It combines two search methods:

**Semantic search** (embeddings + cosine similarity):
- Finds content by meaning
- "deployment process" matches "how to release"
- Can miss exact keyword matches if the embedding space doesn't place them close

**BM25** (keyword search):
- A statistical text retrieval algorithm used in search engines since the 1990s
- Scores documents based on term frequency (how often query words appear) and inverse document frequency (how rare those words are across all documents)
- Great at exact matches: "Kubernetes" always finds documents containing "Kubernetes"
- Misses semantic relationships: "container orchestration" won't match "Kubernetes"

**Reciprocal Rank Fusion (RRF):** SecondBrain merges both result lists using RRF. For each document, the score is:

```
score = 1/(k + rank_semantic) + 1/(k + rank_bm25)
```

Where `k=60` is a constant that prevents top-ranked results from dominating too heavily. A document ranked #1 by both methods gets a higher combined score than one ranked #1 by only one method.

**Why hybrid is better than either alone:** Benchmarks consistently show that hybrid search outperforms pure semantic or pure keyword search by 5-15% on retrieval accuracy. You get the "meaning match" capability of embeddings plus the "exact match" reliability of keywords.

### ChromaDB — The Vector Database

ChromaDB is an open-source, embedded vector database. "Embedded" means it runs inside your Python process — no separate server, no Docker container, no cloud account.

**How it stores data:**
- Vectors are indexed using HNSW (Hierarchical Navigable Small World graphs)
- Documents, metadata, and IDs are stored alongside the vectors
- Everything persists to disk in `data/chroma/`

**HNSW explained:** Imagine a multi-layered graph where each layer is progressively sparser. The top layer has a few well-connected "highway" nodes. When you search, you start at the top layer and greedily navigate towards your query vector, then drop to the next layer for finer navigation, and so on until you reach the bottom layer with all nodes. This gives O(log n) search time instead of O(n) brute-force comparison.

**Why ChromaDB and not Pinecone/Weaviate/Qdrant?**
- **Pinecone** — cloud-hosted, requires an API key and account. Great for production, unnecessary for a personal tool
- **Weaviate/Qdrant** — run as separate server processes. More powerful, but adds deployment complexity
- **ChromaDB** — `pip install chromadb`, zero config, runs in-process. The right choice for a local-first personal tool

### SQLite — Metadata Storage

ChromaDB stores vectors and text. SQLite stores everything else:
- Source records (title, type, URL, tags, chunk count, ingestion date)
- Chunk records (text content, ChromaDB IDs per chunk)

This separation means you can browse and manage your sources without touching the vector database. The Sources tab, tagging system, chunk viewer, and re-ingestion all work through SQLite.

### Claude (Anthropic API) — Answer Generation

Claude is the only component that requires an API key and costs money (pay-per-use). SecondBrain uses `claude-sonnet-4-20250514` — fast and cheap enough for personal use.

**What Claude receives:**
```
System: "You are a research assistant. Answer ONLY from the provided context..."

User: "Context:
--- Chunk 1 [Source: AWS Reliability] ---
The reliability pillar includes the ability to...

--- Chunk 2 [Source: AWS Reliability] ---
Design principles for reliability include...

Question: What are the key reliability principles?"
```

**What Claude does NOT receive:** Your entire knowledge base. It only sees the 5 most relevant chunks that the retrieval pipeline selected. This keeps costs low (~$0.001–0.01 per query) and prevents the context window from being overwhelmed.

### Streamlit — The Web UI

Streamlit turns Python scripts into web apps. `app.py` is a regular Python file — Streamlit re-runs it from top to bottom on every user interaction (button click, text input, etc.). Session state persists between re-runs.

**Why Streamlit:** Zero frontend code. No HTML, CSS, JavaScript, React, or build tools. The entire UI is defined in ~280 lines of Python. For a personal tool, this is the right trade-off — you sacrifice customisation for development speed.

### BeautifulSoup — Web Scraping

When you ingest a URL, `requests` fetches the raw HTML and `BeautifulSoup` parses it. The extraction logic:

1. Remove non-content tags (`<script>`, `<style>`, `<nav>`, `<footer>`, `<header>`, `<aside>`)
2. Look for the main content container (`<article>`, `<main>`, `role="main"`, or elements with content-related IDs/classes)
3. Fall back to all `<p>` tags if no container is found
4. Fall back to all text if no `<p>` tags exist

**Limitation:** BeautifulSoup only sees static HTML. Sites that render content via JavaScript (Reddit, many news sites, single-page apps) return minimal text. The app detects this (< 200 characters extracted) and warns you to use Paste text instead.

### pdfplumber — PDF Extraction

pdfplumber reads PDF files and extracts text page by page, including text within tables. It handles multi-column layouts and preserves paragraph structure better than simpler libraries like PyPDF2.

### youtube-transcript-api — YouTube Transcripts

Most YouTube videos have auto-generated captions (YouTube's own speech-to-text). This library calls YouTube's API to fetch those captions as text — no audio download or processing required. The transcript is just text with timestamps, which we join into a single document and ingest normally.

**Cloud limitation:** YouTube blocks requests from cloud provider IPs. YouTube ingestion works locally but not from Streamlit Cloud.

---

## How It Works

### Architecture

```
┌──────────────┐     ┌──────────────┐     ┌───────────┐
│  Streamlit   │───▶ │  Ingest      │────▶│ ChromaDB  │
│  UI (app.py) │     │  Pipeline    │     │ (vectors) │
│              │     │  (ingest.py) │     └───────────┘
│              │     └──────────────┘           │
│              │                                │
│              │     ┌──────────────┐           │
│              │───▶ │  Query       │◀──────────┘
│              │     │  Pipeline    │
│              │     │  (query.py)  │────▶ Claude API
│              │     └──────────────┘     (answer gen)
│              │
│              │     ┌──────────────┐
│              │───▶ │  SQLite      │
│              │     │  (db.py)     │
└──────────────┘     └──────────────┘
```

### Ingestion Pipeline (ingest.py)

1. **Input**: Raw text, URL, PDF file, YouTube URL, or bulk URL list
2. **Extraction**: URLs → BeautifulSoup; PDFs → pdfplumber; YouTube → transcript API
3. **Chunking**: Recursive splitter (headings → paragraphs → sentences → words) with ~50-token overlap
4. **Embedding**: Each chunk is embedded using `all-MiniLM-L6-v2` via sentence-transformers
5. **Storage**: Chunks + embeddings → ChromaDB. Chunk text + metadata → SQLite
6. **Tagging**: Optional tags attached to sources for filtered retrieval

### Query Pipeline (query.py)

1. **Embed the question**: `all-MiniLM-L6-v2` encodes your question into a 384-d vector
2. **Semantic retrieval**: ChromaDB cosine similarity search returns top 10 candidates
3. **BM25 retrieval**: Keyword scoring over the same candidate set
4. **Reciprocal Rank Fusion**: Merges semantic + BM25 rankings into one list
5. **Reranking** (optional): Cross-encoder re-scores top 10 → keeps top 5
6. **Tag filtering**: If tags are selected, only chunks from matching sources are searched
7. **Prompt construction**: System prompt + retrieved chunks + question → Claude
8. **Generation**: Claude produces a grounded answer with source citations
9. **Conversation history**: Prior turns are included for multi-turn follow-ups

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| UI | Streamlit | Web interface on localhost |
| Vector DB | ChromaDB | Stores and searches embeddings locally |
| Embeddings | sentence-transformers / all-MiniLM-L6-v2 | Converts text to 384-d vectors, runs locally |
| Reranking | sentence-transformers / ms-marco-MiniLM-L-6-v2 | Cross-encoder reranking for precision (optional) |
| Keyword search | Custom BM25 implementation | Keyword scoring for hybrid search |
| LLM | Claude via Anthropic API | Generates answers from retrieved context |
| Metadata | SQLite | Tracks sources, chunks, and tags |
| Web scraping | BeautifulSoup + requests | Extracts text from URLs |
| PDF extraction | pdfplumber | Extracts text from PDF files |
| YouTube | youtube-transcript-api | Fetches video transcripts |
| CI | GitHub Actions | Linting, import checks, tests on every push |

---

## Features

### Ingestion
- **Paste text** — copy-paste anything, give it a title
- **URL** — fetches and extracts web page content (with JS-rendering detection)
- **File upload** — PDF, DOCX, TXT, Markdown, CSV, JSON, and RST files
- **YouTube** — pulls auto-generated or community transcripts (local only)
- **Bulk URLs** — paste a list of URLs, ingest them all at once
- **Tagging** — tag sources on ingest or edit tags later
- **KB import** — import a previously exported SecondBrain knowledge base

### Retrieval
- **Hybrid search** — combines semantic (embedding) and keyword (BM25) search via Reciprocal Rank Fusion
- **Cross-encoder reranking** — optional second-pass ranking for higher precision
- **Tag filtering** — scope queries to specific topics
- **Conversation history** — multi-turn Q&A within a session
- **Streaming responses** — answers appear token by token as Claude generates them
- **Model picker** — choose between Claude Sonnet 4 (default) or Haiku 3.5 (fast/cheap)

### Source Management
- **View all chunks** for any source
- **Edit tags** inline
- **Summarise** — AI-generated bullet-point summary of any source
- **Re-ingest** — re-embed all chunks (useful after switching embedding models)
- **Delete** — removes source + all vectors from ChromaDB and SQLite
- **Export KB** — download your entire knowledge base as a JSON file for backup or migration

### Analytics & History
- **Search history** — browse, review, and re-ask past queries
- **KB analytics** — total sources, chunks, queries, source type breakdown, tag frequency
- **Duplicate detection** — scan for near-duplicate chunks using cosine similarity on embeddings

### Output
- **Markdown export** — download the last answer + sources as a `.md` file
- **Source transparency** — every answer shows which chunks were used and their relevance scores

---

## Setup

### Prerequisites

- Python 3.11+
- An Anthropic API key ([console.anthropic.com](https://console.anthropic.com))

### Installation

```bash
# Clone the repo
git clone https://github.com/PhiSmi/SecondBrain.git
cd SecondBrain

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up your API key
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### Running

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`.

### Deploying to Streamlit Cloud

1. Push your repo to GitHub (private repo works)
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with GitHub
3. Grant Streamlit access to your repo
4. Set main file to `app.py`
5. Add secrets in the app settings:
   ```toml
   APP_PASSWORD = "your-password"
   ANTHROPIC_API_KEY = "your-key"
   ```

**Cloud limitations:** YouTube and some websites (Reddit, etc.) block cloud provider IPs. Use Paste text or PDF upload for those.

---

## Project Structure

```
SecondBrain/
├── .github/
│   └── workflows/
│       └── ci.yml              # GitHub Actions CI pipeline
├── .streamlit/
│   ├── config.toml             # Streamlit server config (file watcher, logging)
│   ├── secrets.toml            # Local secrets (git-ignored)
│   └── secrets.toml.example    # Template for secrets
├── app.py                      # Streamlit UI — Ingest, Ask, History, Sources, Analytics tabs
├── ingest.py                   # Ingestion pipeline — all content types + chunking + export/import
├── query.py                    # Retrieval — hybrid search, reranking, streaming generation
├── db.py                       # SQLite — sources, chunks, tags, search history, analytics
├── requirements.txt            # Python dependencies
├── .env                        # Anthropic API key (git-ignored)
├── .env.example                # Template for .env
├── .gitignore
└── data/                       # Local data (git-ignored)
    ├── chroma/                 # ChromaDB vector storage
    └── metadata.db             # SQLite metadata
```

---

## Configuration

| Parameter | File | Default | Description |
|-----------|------|---------|-------------|
| `CHUNK_SIZE` | ingest.py | 500 | Target tokens per chunk |
| `CHUNK_OVERLAP` | ingest.py | 50 | Overlap tokens between adjacent chunks |
| `TOP_K` | query.py | 10 | Candidates retrieved before reranking |
| `FINAL_K` | query.py | 5 | Chunks sent to Claude after reranking |
| `RRF_K` | query.py | 60 | RRF merge constant |
| `model` | query.py / app.py | claude-sonnet-4-20250514 | Claude model for answer generation (selectable in UI) |

---

## CI/CD

GitHub Actions runs on every push and pull request to `main`:

1. **Matrix build** — tests against Python 3.11, 3.12, and 3.13
2. **Dependency caching** — pip packages are cached to speed up runs
3. **Linting** — `ruff check .` catches style issues and common bugs
4. **Import verification** — ensures all modules load without errors
5. **Tests** — runs `pytest` (gracefully skips if no tests exist yet)

---

## Current Limitations

- **Cloud IP blocking** — YouTube, Reddit, and some news sites block requests from cloud provider IPs. Use Paste text or file upload on Streamlit Cloud
- **Static HTML only for URLs** — JavaScript-rendered pages return minimal content. The app detects this and warns you
- **1GB RAM on Streamlit Cloud** — reranking is off by default to avoid out-of-memory crashes. Enable it locally
- **No authentication beyond password gate** — the password check is a simple gate, not production-grade auth
- **Session-scoped conversation** — chat history exists within a session but search history is persisted in SQLite

---

## License

MIT
