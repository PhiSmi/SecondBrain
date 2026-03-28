# SecondBrain

A local, privacy-first knowledge base powered by RAG (Retrieval-Augmented Generation). Paste text or URLs, and ask questions in natural language — get answers grounded in your own content, with source citations.

---

## TL;DR

1. Paste text or a URL into the app
2. It gets chunked and embedded into a local vector database
3. Ask questions in plain English
4. Get AI-generated answers with references to exactly which sources the answer came from

No cloud storage. No data leaves your machine (except the query to Claude for answer generation). Everything else runs locally.

---

## What It Is and How It Works

SecondBrain is a personal knowledge management tool that turns unstructured text into a searchable, queryable knowledge base. Think of it as a personal research assistant that only knows what you've fed it.

### The 30-Second Version

You have articles, notes, and web pages scattered everywhere. You want to ask "What did I read about X?" and get a real answer — not a list of links, but an actual synthesised response pointing to the exact sources.

SecondBrain does this in two steps:

**Step 1 — You feed it content.** Paste text or give it a URL. Behind the scenes, the app breaks the text into small chunks, converts each chunk into a mathematical representation of its meaning (an "embedding"), and stores everything in a local database on your machine.

**Step 2 — You ask questions.** Type a question in plain English. The app converts your question into the same mathematical form, finds the stored chunks whose meaning is closest to your question, sends those chunks to Claude (Anthropic's AI), and Claude writes you an answer using *only* that content — with citations back to the original sources.

This pattern is called **RAG** (Retrieval-Augmented Generation):

- **Retrieval**: Finding the most relevant chunks of your stored content using semantic similarity search
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

SecondBrain uses a simple but effective chunking strategy:

1. **Split by paragraphs first** — natural boundaries in the text
2. **Split by sentences if a paragraph is too long** — keeps chunks under the target size (~500 tokens)
3. **Overlap between chunks** (~50 tokens) — if a key sentence falls right on the boundary between chunk 2 and chunk 3, it appears in both, so it's never lost

**Why ~500 tokens?** It's a sweet spot. Too small (50 tokens) and you lose context — the chunk might be a single sentence ripped from its paragraph. Too large (2,000 tokens) and the embedding becomes a blurry average of too many ideas, making retrieval less precise. 500 tokens is roughly a solid paragraph or two — enough context to be meaningful, focused enough to embed well.

### What Is an LLM (Large Language Model)?

An LLM is a neural network trained on vast amounts of text that can generate human-like responses. In SecondBrain, Claude (by Anthropic) serves as the answer generator. It doesn't search your knowledge base — it receives the already-retrieved chunks as context and synthesizes them into a coherent answer.

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

In practice, most text embeddings fall between 0.3 and 0.9. A score of 0.75+ usually indicates strong relevance. SecondBrain returns the top 5 chunks by similarity and shows you the score so you can judge how relevant each source is.

Cosine similarity is preferred over Euclidean distance for text because it's **magnitude-invariant** — it cares about the direction of the vector (what the text means), not its length (how long the text is).

### What Is a System Prompt?

When you call an LLM API, you can provide a "system prompt" — instructions that shape how the model behaves for the entire conversation. It's like giving the model a job description before it starts answering.

SecondBrain's system prompt tells Claude:
> "You are a helpful research assistant. Answer based ONLY on the provided context. Cite your sources. If the context doesn't have the answer, say so."

This is critical for RAG. Without this constraint, the model might blend its training knowledge with the retrieved context, making it impossible to trace where an answer came from.

---

## How It Works

### Architecture

```
┌─────────────┐     ┌──────────────┐     ┌───────────┐
│  Streamlit   │────▶│  Ingest      │────▶│ ChromaDB  │
│  UI (app.py) │     │  Pipeline    │     │ (vectors) │
│              │     │  (ingest.py) │     └───────────┘
│              │     └──────────────┘           │
│              │                                │
│              │     ┌──────────────┐           │
│              │────▶│  Query       │◀──────────┘
│              │     │  Pipeline    │
│              │     │  (query.py)  │────▶ Claude API
│              │     └──────────────┘     (answer gen)
│              │
│              │     ┌──────────────┐
│              │────▶│  SQLite      │
│              │     │  (db.py)     │
└─────────────┘     └──────────────┘
```

### Ingestion Pipeline (ingest.py)

1. **Input**: Raw text or a URL
2. **Extraction**: For URLs, fetches the page and strips HTML/nav/footer using BeautifulSoup
3. **Chunking**: Splits text into ~500-token chunks with ~50-token overlap. Splits by paragraph first, then by sentence for oversized paragraphs
4. **Embedding**: Each chunk is embedded using `all-MiniLM-L6-v2` from sentence-transformers — a lightweight model that runs locally, no API key needed
5. **Storage**: Chunks + embeddings go into ChromaDB (a local vector database stored in `data/chroma/`). Metadata (source title, URL, chunk index) is attached to each chunk
6. **Logging**: Source metadata (title, type, URL, chunk count, timestamp) is recorded in SQLite (`data/metadata.db`)

### Query Pipeline (query.py)

1. **Embed the question**: Same `all-MiniLM-L6-v2` model encodes your question into a vector
2. **Retrieve**: ChromaDB performs cosine similarity search, returning the top 5 most relevant chunks
3. **Build prompt**: A system prompt instructs Claude to answer *only* from the provided context and cite sources. The retrieved chunks are injected as context
4. **Generate**: Claude (`claude-sonnet-4-20250514`) produces a grounded answer with source citations
5. **Display**: The answer and source chunks are shown in the Streamlit UI

### Embedding Model: all-MiniLM-L6-v2

- **384-dimensional** embeddings
- **~80MB** model size — downloads once, runs locally
- Optimized for semantic similarity (trained on 1B+ sentence pairs)
- Fast inference on CPU — no GPU required
- Good enough for a personal knowledge base; production systems might use larger models

### Vector Database: ChromaDB

- Stores embeddings persistently in `data/chroma/`
- Uses HNSW (Hierarchical Navigable Small World) index for fast approximate nearest-neighbour search
- Cosine similarity metric for comparing query and document embeddings
- Zero configuration — no server process, just a local folder

### Metadata: SQLite

- Tracks ingested sources in `data/metadata.db`
- Records: title, source type (text/URL), URL, chunk count, ingestion timestamp
- Enables the Sources tab for managing what's in your knowledge base

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| UI | Streamlit | Web interface on localhost |
| Vector DB | ChromaDB | Stores and searches embeddings locally |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | Converts text to vectors, runs locally |
| LLM | Claude via Anthropic API | Generates answers from retrieved context |
| Metadata | SQLite | Tracks ingested sources |
| Web scraping | BeautifulSoup + requests | Extracts text from URLs |
| CI | GitHub Actions | Linting, import checks, tests on every push |

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

---

## Usage

### Ingesting Content

1. Go to the **Ingest** tab
2. Choose **Paste text** or **URL**
3. For text: give it a title and paste the content
4. For URLs: enter the URL (title is optional)
5. Click **Ingest** — the text is chunked, embedded, and stored

### Asking Questions

1. Go to the **Ask** tab
2. Type your question in natural language
3. Click **Ask**
4. Get an answer with source citations
5. Expand the sources to see the exact chunks that informed the answer

### Managing Sources

The **Sources** tab shows everything you've ingested: title, type, chunk count, and date. You can delete sources you no longer need.

---

## Project Structure

```
SecondBrain/
├── .github/
│   └── workflows/
│       └── ci.yml          # GitHub Actions CI pipeline
├── app.py                  # Streamlit UI — three tabs: Ingest, Ask, Sources
├── ingest.py               # Chunking + embedding pipeline
├── query.py                # Retrieval + Claude answer generation
├── db.py                   # SQLite metadata helpers
├── requirements.txt        # Python dependencies
├── .env                    # Your Anthropic API key (git-ignored)
├── .env.example            # Template for .env
├── .gitignore
└── data/                   # Local data (git-ignored)
    ├── chroma/             # ChromaDB vector storage
    └── metadata.db         # SQLite source metadata
```

---

## CI/CD

GitHub Actions runs on every push and pull request to `main`:

1. **Matrix build** — tests against Python 3.11 and 3.12
2. **Dependency caching** — pip packages are cached to speed up runs
3. **Linting** — `ruff check .` catches style issues and common bugs
4. **Import verification** — ensures all modules load without errors
5. **Tests** — runs `pytest` (gracefully skips if no tests exist yet)

To set up CI for your fork:
1. Go to your repo on GitHub
2. Navigate to **Settings > Secrets and variables > Actions**
3. Add a secret called `ANTHROPIC_API_KEY` with your API key
4. Push to `main` — the workflow runs automatically

---

## Configuration

Key constants you can tune in the source code:

| Parameter | File | Default | Description |
|-----------|------|---------|-------------|
| `CHUNK_SIZE` | ingest.py | 500 | Target tokens per chunk |
| `CHUNK_OVERLAP` | ingest.py | 50 | Overlap tokens between chunks |
| `TOP_K` | query.py | 5 | Number of chunks to retrieve per query |
| `model` | query.py | claude-sonnet-4-20250514 | Claude model for answer generation |

---

## Iteration Roadmap

This is the MVP. Future iterations:

| Iteration | Feature |
|-----------|---------|
| 2 | PDF upload (PyPDF2 / pdfplumber) |
| 3 | Tagging and filtering (search within specific topics) |
| 4 | Better chunking (recursive text splitter) |
| 5 | Source management (re-ingest, view all chunks from a source) |
| 6 | Conversation history (multi-turn Q&A) |
| 7 | Export answers to markdown/notes |

---

## Limitations

- **Localhost only** — no authentication, not meant for deployment
- **No PDF support yet** — text and URLs only in MVP
- **Simple chunking** — paragraph-based splitting; doesn't handle tables or code blocks specially
- **Single embedding model** — no reranking or hybrid search
- **No conversation memory** — each question is independent

---

## License

MIT
