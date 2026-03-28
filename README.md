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

## What It Is

SecondBrain is a personal knowledge management tool that turns unstructured text into a searchable, queryable knowledge base. It uses the **RAG** (Retrieval-Augmented Generation) pattern:

- **Retrieval**: When you ask a question, it finds the most relevant chunks of your stored content using semantic similarity search
- **Augmented Generation**: Those chunks are passed as context to Claude (Anthropic's LLM), which generates a grounded answer — not hallucinated, not from its training data, but from *your* content

Think of it as a personal research assistant that only knows what you've fed it.

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
- Uses HNSW (Hierarchical Navigable Small World) index for fast approximate nearest-neighbor search
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

---

## Setup

### Prerequisites

- Python 3.11+
- An Anthropic API key ([console.anthropic.com](https://console.anthropic.com))

### Installation

```bash
# Clone the repo
git clone https://github.com/yourusername/SecondBrain.git
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
├── app.py              # Streamlit UI — three tabs: Ingest, Ask, Sources
├── ingest.py           # Chunking + embedding pipeline
├── query.py            # Retrieval + Claude answer generation
├── db.py               # SQLite metadata helpers
├── requirements.txt    # Python dependencies
├── .env                # Your Anthropic API key (git-ignored)
├── .gitignore
└── data/               # Local data (git-ignored)
    ├── chroma/         # ChromaDB vector storage
    └── metadata.db     # SQLite source metadata
```

---

## How RAG Works (The Deeper Explanation)

RAG solves a fundamental problem with LLMs: they can only answer from their training data, which is frozen at a point in time and doesn't include your private content.

### The Problem

If you ask Claude "What are our team's deployment best practices?", it has no idea — that information isn't in its training data. You could paste the entire document into the prompt, but that doesn't scale when you have dozens or hundreds of documents.

### The Solution

RAG adds a **retrieval** step before generation:

1. **Offline (ingestion)**: Convert all your documents into numerical vectors (embeddings) that capture semantic meaning. Store them in a vector database.

2. **Online (query time)**:
   - Convert your question into the same kind of vector
   - Find the stored vectors most similar to your question vector (semantic search)
   - Pass those matching text chunks to the LLM as context
   - The LLM generates an answer grounded in your actual content

### Why Chunking Matters

LLMs have limited context windows, and embedding models work best on shorter text. Chunking breaks long documents into digestible pieces (~500 tokens each). The overlap between chunks ensures that information spanning a chunk boundary isn't lost.

### Why Embeddings Matter

Embeddings convert text into dense numerical vectors where **semantic similarity maps to geometric proximity**. "How do I deploy to production?" and "Our deployment process involves..." will have similar vectors, even though they share few words. This enables semantic search — finding content by meaning, not just keywords.

### Why the LLM Matters

The retrieved chunks alone could answer your question, but reading raw text chunks isn't great UX. The LLM synthesizes them into a coherent, natural-language answer and can cross-reference multiple sources. The system prompt constrains it to only use the provided context, reducing hallucination.

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
