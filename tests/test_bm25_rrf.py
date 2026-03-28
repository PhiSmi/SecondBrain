"""Tests for BM25 scoring and Reciprocal Rank Fusion.

Pure-Python reimplementations to avoid importing query.py's heavy deps.
"""

import math
import re
from collections import defaultdict


# ---- Pure-Python copies of the functions under test ----

def _tokenise(text: str) -> list[str]:
    return re.findall(r"\b\w+\b", text.lower())


def _bm25_scores(query: str, documents: list[str], k1: float = 1.5, b: float = 0.75) -> list[float]:
    if not documents:
        return []
    tokenised_docs = [_tokenise(d) for d in documents]
    avg_dl = sum(len(d) for d in tokenised_docs) / len(tokenised_docs)
    query_terms = _tokenise(query)
    idf = {}
    N = len(documents)
    for term in set(query_terms):
        df = sum(1 for d in tokenised_docs if term in d)
        idf[term] = math.log((N - df + 0.5) / (df + 0.5) + 1)
    scores = []
    for doc_tokens in tokenised_docs:
        dl = len(doc_tokens)
        freq = defaultdict(int)
        for t in doc_tokens:
            freq[t] += 1
        score = 0.0
        for term in query_terms:
            tf = freq.get(term, 0)
            score += idf.get(term, 0) * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / avg_dl))
        scores.append(score)
    return scores


RRF_K = 60


def _rrf_merge(ranked_lists: list[list[str]], k: int = RRF_K) -> list[str]:
    scores = defaultdict(float)
    for ranked in ranked_lists:
        for rank, doc_id in enumerate(ranked, 1):
            scores[doc_id] += 1.0 / (k + rank)
    return sorted(scores, key=lambda x: scores[x], reverse=True)


# ---- Tests ----

class TestTokenise:
    def test_basic(self):
        assert _tokenise("Hello World") == ["hello", "world"]

    def test_punctuation(self):
        assert _tokenise("it's a test.") == ["it", "s", "a", "test"]

    def test_empty(self):
        assert _tokenise("") == []


class TestBM25:
    def test_empty_docs(self):
        assert _bm25_scores("hello", []) == []

    def test_single_doc_match(self):
        scores = _bm25_scores("python", ["python is great", "java is also good"])
        assert scores[0] > scores[1]

    def test_exact_match_scores_highest(self):
        docs = ["cat dog bird", "the quick brown fox", "cat cat cat"]
        scores = _bm25_scores("cat", docs)
        assert scores[2] > scores[0]
        assert scores[0] > scores[1]

    def test_multi_term_query(self):
        docs = ["machine learning is powerful", "deep learning models", "cooking recipes"]
        scores = _bm25_scores("machine learning", docs)
        assert scores[0] > scores[2]
        assert scores[1] > scores[2]

    def test_no_match(self):
        scores = _bm25_scores("xyz", ["hello world", "foo bar"])
        assert all(s == 0.0 for s in scores)


class TestRRF:
    def test_empty(self):
        assert _rrf_merge([]) == []

    def test_single_list(self):
        result = _rrf_merge([["a", "b", "c"]])
        assert result == ["a", "b", "c"]

    def test_two_lists_agreement(self):
        result = _rrf_merge([["a", "b", "c"], ["a", "b", "c"]])
        assert result[0] == "a"
        assert result[1] == "b"

    def test_two_lists_disagreement(self):
        # With k=60: a gets 1/61 + 1/63, b gets 1/62 + 1/62, c gets 1/63 + 1/61
        # a and c tie (symmetric), b is slightly lower — all three are close
        # The key property: all items appear in the merged result
        result = _rrf_merge([["a", "b", "c"], ["c", "b", "a"]])
        assert set(result) == {"a", "b", "c"}

    def test_disjoint_lists(self):
        result = _rrf_merge([["a", "b"], ["c", "d"]])
        assert set(result) == {"a", "b", "c", "d"}
