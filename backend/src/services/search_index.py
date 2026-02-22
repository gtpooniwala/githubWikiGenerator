"""Keyword search index over repo chunks.

Implements BM25 scoring for ranked retrieval.  Falls back to simple substring
matching when BM25 yields no results (e.g. very small corpora or exact-phrase
queries that BM25 would score near zero).

Usage::

    idx = SearchIndex()
    idx.add_chunks(chunks)          # list[Chunk] from services.chunker
    results = idx.search("login", k=5)  # -> list[SearchResult]
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from collections import defaultdict
from typing import Iterable

from services.chunker import Chunk

# ---------------------------------------------------------------------------
# BM25 hyper-parameters (standard defaults)
# ---------------------------------------------------------------------------

_K1: float = 1.5   # term-frequency saturation
_B: float = 0.75   # length normalisation factor


def _tokenise(text: str) -> list[str]:
    """Lower-case, split on word boundaries, drop pure-digit tokens."""
    return [t for t in re.findall(r"[a-z_][a-z0-9_]*", text.lower()) if t]


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass
class SearchResult:
    chunk_id: str
    path: str
    start_line: int
    end_line: int
    text: str
    score: float


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------


class SearchIndex:
    """BM25 search index over a corpus of :class:`~services.chunker.Chunk` objects."""

    def __init__(self) -> None:
        # chunk_id → Chunk
        self._chunks: dict[str, Chunk] = {}
        # term → {chunk_id: count}
        self._tf: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        # chunk_id → token count
        self._lengths: dict[str, int] = {}
        # built lazily
        self._idf: dict[str, float] = {}
        self._avg_dl: float = 0.0
        self._built: bool = False

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def add_chunk(self, chunk: Chunk) -> None:
        """Add a single chunk to the index."""
        self._built = False
        self._chunks[chunk.chunk_id] = chunk
        tokens = _tokenise(chunk.text)
        self._lengths[chunk.chunk_id] = len(tokens)
        for token in tokens:
            self._tf[token][chunk.chunk_id] += 1

    def add_chunks(self, chunks: Iterable[Chunk]) -> None:
        """Add multiple chunks at once."""
        for chunk in chunks:
            self.add_chunk(chunk)

    # ------------------------------------------------------------------
    # Build (lazy, on first search)
    # ------------------------------------------------------------------

    def _build(self) -> None:
        """Pre-compute IDF values and average document length."""
        n = len(self._chunks)
        if n == 0:
            self._avg_dl = 0.0
            self._idf = {}
            self._built = True
            return

        self._avg_dl = sum(self._lengths.values()) / n

        self._idf = {}
        for term, postings in self._tf.items():
            df = len(postings)
            # Robertson-Sparck Jones IDF (with smoothing to avoid negatives)
            self._idf[term] = math.log((n - df + 0.5) / (df + 0.5) + 1.0)

        self._built = True

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str, k: int = 10) -> list[SearchResult]:
        """Return up to *k* results ranked by BM25 score.

        Falls back to case-insensitive substring match when BM25 yields zero
        results (handles exact-symbol queries that may not tokenise well).
        """
        if not self._built:
            self._build()

        if not self._chunks:
            return []

        query_terms = _tokenise(query)
        if not query_terms:
            return []

        scores: dict[str, float] = defaultdict(float)

        for term in query_terms:
            if term not in self._tf:
                continue
            idf = self._idf.get(term, 0.0)
            postings = self._tf[term]
            for cid, tf_val in postings.items():
                dl = self._lengths[cid]
                avgdl = self._avg_dl if self._avg_dl > 0 else 1.0
                norm = 1 - _B + _B * dl / avgdl
                tf_norm = (tf_val * (_K1 + 1)) / (tf_val + _K1 * norm)
                scores[cid] += idf * tf_norm

        top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:k]

        # Fallback: substring match if BM25 gave nothing
        if not top:
            return self._substring_search(query, k)

        return [self._to_result(cid, score) for cid, score in top]

    def _substring_search(self, query: str, k: int) -> list[SearchResult]:
        """Case-insensitive substring search as a fallback."""
        q_lower = query.lower()
        matches: list[SearchResult] = []
        for cid, chunk in self._chunks.items():
            if q_lower in chunk.text.lower():
                matches.append(self._to_result(cid, 0.0))
            if len(matches) >= k:
                break
        return matches

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _to_result(self, chunk_id: str, score: float) -> SearchResult:
        chunk = self._chunks[chunk_id]
        return SearchResult(
            chunk_id=chunk.chunk_id,
            path=chunk.path,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            text=chunk.text,
            score=score,
        )

    # ------------------------------------------------------------------
    # Convenience factory
    # ------------------------------------------------------------------

    @classmethod
    def from_chunks(cls, chunks: Iterable[Chunk]) -> "SearchIndex":
        """Create and populate an index in one call."""
        idx = cls()
        idx.add_chunks(chunks)
        return idx
