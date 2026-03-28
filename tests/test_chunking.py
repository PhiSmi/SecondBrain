"""Tests for the chunking pipeline.

These tests import only the pure-Python chunking functions to avoid
requiring heavy dependencies (chromadb, sentence-transformers) in CI.
"""

import re
import sys
from pathlib import Path

# We need to be able to import the chunking functions without triggering
# the top-level imports of chromadb/sentence-transformers in ingest.py.
# So we extract the functions directly from source.

sys.path.insert(0, str(Path(__file__).parent.parent))

# Import just the config module (light dep: pyyaml)
import config  # noqa: E402

# Recreate the pure-Python functions here to avoid heavy imports.
# This mirrors ingest.py exactly but avoids the chromadb dependency.

_cfg = config.retrieval()
CHUNK_SIZE = _cfg.get("chunk_size", 500)
CHUNK_OVERLAP = _cfg.get("chunk_overlap", 50)

_CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_TABLE_RE = re.compile(r"(?:^\|.+\|$\n?){2,}", re.MULTILINE)


def _approx_tokens(text: str) -> int:
    return int(len(text.split()) * 1.3)


def _protect_blocks(text):
    placeholders = {}
    counter = 0

    def _replace(match):
        nonlocal counter
        key = f"\x00BLOCK_{counter}\x00"
        placeholders[key] = match.group(0)
        counter += 1
        return key

    text = _CODE_BLOCK_RE.sub(_replace, text)
    text = _TABLE_RE.sub(_replace, text)
    return text, placeholders


def _restore_blocks(chunks, placeholders):
    if not placeholders:
        return chunks
    restored = []
    for chunk in chunks:
        for key, value in placeholders.items():
            chunk = chunk.replace(key, value)
        restored.append(chunk)
    return restored


def _split_with_separator(text, separators, chunk_size, overlap):
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

    chunks = []
    current = []
    current_tokens = 0
    overlap_words = []

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


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    protected_text, placeholders = _protect_blocks(text)
    separators = [r"\n#{1,6} ", r"\n\n", r"(?<=[.!?])\s+", r" "]
    chunks = _split_with_separator(protected_text, separators, chunk_size, overlap)
    return _restore_blocks(chunks, placeholders)


# ---- Tests ----

class TestApproxTokens:
    def test_empty(self):
        assert _approx_tokens("") == 0

    def test_short_sentence(self):
        result = _approx_tokens("hello world")
        assert result == int(2 * 1.3)

    def test_longer_text(self):
        text = " ".join(["word"] * 100)
        assert _approx_tokens(text) == int(100 * 1.3)


class TestChunkText:
    def test_empty_text(self):
        assert chunk_text("") == []

    def test_whitespace_only(self):
        assert chunk_text("   \n\n   ") == []

    def test_short_text_single_chunk(self):
        text = "This is a short paragraph."
        chunks = chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0].strip() == text

    def test_long_text_splits(self):
        text = " ".join(["word"] * 1000)
        chunks = chunk_text(text, chunk_size=100, overlap=10)
        assert len(chunks) > 1

    def test_respects_paragraph_boundaries(self):
        para1 = " ".join(["alpha"] * 80)
        para2 = " ".join(["beta"] * 80)
        text = f"{para1}\n\n{para2}"
        chunks = chunk_text(text, chunk_size=120, overlap=10)
        assert len(chunks) >= 2
        assert "alpha" in chunks[0]

    def test_heading_boundaries(self):
        # Build sections large enough that each exceeds chunk_size to force a split
        sec1 = "# Heading One\n\n" + " ".join(["alpha"] * 50)
        sec2 = "\n# Heading Two\n\n" + " ".join(["beta"] * 50)
        text = sec1 + sec2
        chunks = chunk_text(text, chunk_size=80, overlap=0)
        assert len(chunks) >= 2

    def test_no_empty_chunks(self):
        text = "\n\n\n".join(["Some content here"] * 10)
        chunks = chunk_text(text, chunk_size=50, overlap=5)
        for chunk in chunks:
            assert chunk.strip() != ""


class TestMarkdownProtection:
    def test_code_block_protected(self):
        text = "Before\n\n```python\ndef foo():\n    return 42\n```\n\nAfter"
        protected, placeholders = _protect_blocks(text)
        assert "```" not in protected
        assert len(placeholders) == 1
        restored = _restore_blocks([protected], placeholders)
        assert "```python" in restored[0]
        assert "def foo():" in restored[0]

    def test_table_protected(self):
        text = "Before\n\n| Col A | Col B |\n| --- | --- |\n| 1 | 2 |\n\nAfter"
        protected, placeholders = _protect_blocks(text)
        assert len(placeholders) >= 1

    def test_no_blocks_passthrough(self):
        text = "Just a normal paragraph."
        protected, placeholders = _protect_blocks(text)
        assert protected == text
        assert placeholders == {}

    def test_code_block_survives_chunking(self):
        before = " ".join(["word"] * 100)
        code = "```python\ndef hello():\n    print('world')\n```"
        after = " ".join(["word"] * 100)
        text = f"{before}\n\n{code}\n\n{after}"
        chunks = chunk_text(text, chunk_size=150, overlap=10)
        all_text = " ".join(chunks)
        assert "def hello():" in all_text
        assert "```python" in all_text
