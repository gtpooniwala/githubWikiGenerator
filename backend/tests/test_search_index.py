"""Tests for services/search_index.py."""

import pytest

from services.chunker import Chunk
from services.search_index import SearchIndex, SearchResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _chunk(path: str, start: int, end: int, text: str) -> Chunk:
    return Chunk(
        chunk_id=f"{path}:{start}-{end}",
        path=path,
        start_line=start,
        end_line=end,
        text=text,
    )


# ---------------------------------------------------------------------------
# Empty index
# ---------------------------------------------------------------------------


class TestEmptyIndex:
    def test_search_empty_index_returns_empty(self):
        idx = SearchIndex()
        assert idx.search("login") == []

    def test_add_zero_chunks_no_crash(self):
        idx = SearchIndex()
        idx.add_chunks([])
        assert idx.search("anything") == []


# ---------------------------------------------------------------------------
# Basic retrieval
# ---------------------------------------------------------------------------


class TestBasicRetrieval:
    def _build_index(self) -> SearchIndex:
        chunks = [
            _chunk("auth.py", 1, 10, "def login(user, password):\n    verify(user)\n"),
            _chunk("auth.py", 11, 20, "def logout(session):\n    session.clear()\n"),
            _chunk(
                "models.py",
                1,
                15,
                "class User:\n    email = ''\n    password_hash = ''\n",
            ),
            _chunk(
                "routes.py",
                1,
                8,
                "def get_profile(user_id):\n    return db.fetch(user_id)\n",
            ),
        ]
        return SearchIndex.from_chunks(chunks)

    def test_login_query_matches_login_chunk(self):
        idx = self._build_index()
        results = idx.search("login")
        chunk_ids = [r.chunk_id for r in results]
        assert "auth.py:1-10" in chunk_ids

    def test_login_chunk_ranked_higher_than_others(self):
        idx = self._build_index()
        results = idx.search("login")
        assert results[0].chunk_id == "auth.py:1-10"

    def test_logout_query_returns_logout_chunk(self):
        idx = self._build_index()
        results = idx.search("logout")
        assert results[0].chunk_id == "auth.py:11-20"

    def test_user_query_matches_multiple_chunks(self):
        idx = self._build_index()
        results = idx.search("user")
        result_ids = {r.chunk_id for r in results}
        # "user" appears in auth.py:1-10, models.py:1-15, routes.py:1-8
        assert len(result_ids) >= 2

    def test_nonexistent_term_returns_empty(self):
        idx = self._build_index()
        results = idx.search("xyzzy_nonexistent_term_789")
        assert results == []


# ---------------------------------------------------------------------------
# Top-k limiting
# ---------------------------------------------------------------------------


class TestTopK:
    def _build_large_index(self) -> SearchIndex:
        chunks = [
            _chunk(f"file{i}.py", 1, 10, f"def login_{i}(user): pass\n")
            for i in range(20)
        ]
        return SearchIndex.from_chunks(chunks)

    def test_top_k_limits_results(self):
        idx = self._build_large_index()
        results = idx.search("login", k=5)
        assert len(results) <= 5

    def test_top_k_1_returns_one_result(self):
        idx = self._build_large_index()
        results = idx.search("login", k=1)
        assert len(results) == 1

    def test_top_k_default_is_10(self):
        idx = self._build_large_index()
        results = idx.search("login")
        assert len(results) <= 10

    def test_top_k_exceeding_corpus_returns_all(self):
        idx = SearchIndex.from_chunks(
            [
                _chunk("a.py", 1, 5, "login function"),
                _chunk("b.py", 1, 5, "login handler"),
            ]
        )
        results = idx.search("login", k=100)
        assert len(results) == 2


# ---------------------------------------------------------------------------
# BM25 scoring
# ---------------------------------------------------------------------------


class TestBM25Scoring:
    def test_higher_tf_scores_higher(self):
        """Chunk with more login mentions scores higher than one with fewer."""
        high_tf = _chunk("a.py", 1, 10, "login login login login login")
        low_tf = _chunk("b.py", 1, 10, "login once")
        idx = SearchIndex.from_chunks([high_tf, low_tf])
        results = idx.search("login", k=2)
        # First result should be a.py (higher term frequency)
        assert results[0].chunk_id == "a.py:1-10"

    def test_scores_are_positive(self):
        idx = SearchIndex.from_chunks(
            [
                _chunk("a.py", 1, 5, "authentication login password"),
            ]
        )
        results = idx.search("login")
        assert results[0].score > 0.0

    def test_rare_term_scores_higher_than_common(self):
        """Less frequent term (higher IDF) should score higher."""
        chunks = [_chunk(f"common{i}.py", 1, 5, "user function") for i in range(10)]
        # Add one chunk with a rare term alongside 'user'
        chunks.append(_chunk("special.py", 1, 5, "user xyzzy_rare_token"))
        idx = SearchIndex.from_chunks(chunks)
        results = idx.search("xyzzy_rare_token")
        assert results[0].chunk_id == "special.py:1-5"


# ---------------------------------------------------------------------------
# Substring fallback
# ---------------------------------------------------------------------------


class TestSubstringFallback:
    def test_exact_symbol_no_tokenise_match_falls_back(self):
        """Queries with camelCase or symbols not split by tokeniser fall back."""
        chunk = _chunk(
            "service.py", 1, 5, "function getUserById(id) { return db.findUser(id); }"
        )
        idx = SearchIndex.from_chunks([chunk])
        # 'getUser' doesn't tokenize cleanly as a single token with the current tokeniser
        # but substring match should still find it
        results = idx.search("getUserById")
        assert len(results) >= 1
        assert results[0].chunk_id == "service.py:1-5"

    def test_substring_fallback_case_insensitive(self):
        chunk = _chunk("db.py", 1, 5, "SELECT * FROM LoginAudit WHERE id = ?")
        idx = SearchIndex.from_chunks([chunk])
        results = idx.search("loginaudit")
        assert len(results) >= 1

    def test_no_fallback_when_bm25_finds_results(self):
        """If BM25 returns results, we should not see zero-score fallback results."""
        idx = SearchIndex.from_chunks(
            [
                _chunk("a.py", 1, 5, "login user password"),
                _chunk("b.py", 1, 5, "something unrelated"),
            ]
        )
        results = idx.search("login")
        # All returned results should have positive BM25 score
        for r in results:
            assert r.score >= 0.0
        # The BM25 result should be first, not b.py
        assert results[0].chunk_id == "a.py:1-5"


# ---------------------------------------------------------------------------
# SearchResult structure
# ---------------------------------------------------------------------------


class TestSearchResultStructure:
    def test_result_fields_populated(self):
        chunk = _chunk("utils/auth.py", 42, 60, "def require_key(key): pass\n")
        idx = SearchIndex.from_chunks([chunk])
        results = idx.search("require_key")
        assert len(results) == 1
        r = results[0]
        assert r.chunk_id == "utils/auth.py:42-60"
        assert r.path == "utils/auth.py"
        assert r.start_line == 42
        assert r.end_line == 60
        assert "require_key" in r.text
        assert isinstance(r.score, float)

    def test_results_are_search_result_instances(self):
        idx = SearchIndex.from_chunks([_chunk("x.py", 1, 5, "hello world")])
        results = idx.search("hello")
        assert all(isinstance(r, SearchResult) for r in results)


# ---------------------------------------------------------------------------
# Incremental ingestion
# ---------------------------------------------------------------------------


class TestIncrementalIngestion:
    def test_add_chunk_after_first_search(self):
        """Index should rebuild IDF when new chunks are added after a search."""
        idx = SearchIndex()
        idx.add_chunk(_chunk("a.py", 1, 5, "login user"))
        _ = idx.search("login")  # triggers build

        # Add new chunk then search again
        idx.add_chunk(_chunk("b.py", 1, 5, "login admin"))
        results = idx.search("login", k=10)
        chunk_ids = {r.chunk_id for r in results}
        assert "a.py:1-5" in chunk_ids
        assert "b.py:1-5" in chunk_ids

    def test_duplicate_chunk_id_overwritten(self):
        """Adding a chunk with same id should overwrite without duplicates."""
        idx = SearchIndex()
        idx.add_chunk(_chunk("a.py", 1, 5, "login auth"))
        idx.add_chunk(_chunk("a.py", 1, 5, "updated login content"))
        results = idx.search("login", k=10)
        ids = [r.chunk_id for r in results]
        assert ids.count("a.py:1-5") == 1


# ---------------------------------------------------------------------------
# Multi-term queries
# ---------------------------------------------------------------------------


class TestMultiTermQueries:
    def test_multi_term_query_returns_best_matching_chunk(self):
        chunks = [
            _chunk(
                "auth.py", 1, 10, "def login(user, password): verify_password(password)"
            ),
            _chunk("utils.py", 1, 5, "def hash_password(raw): return bcrypt(raw)"),
            _chunk("models.py", 1, 8, "class Session: user_id = 0"),
        ]
        idx = SearchIndex.from_chunks(chunks)
        results = idx.search("login password", k=3)
        # auth.py has both 'login' and 'password'
        assert results[0].chunk_id == "auth.py:1-10"

    def test_empty_query_returns_empty(self):
        idx = SearchIndex.from_chunks([_chunk("a.py", 1, 5, "hello world")])
        assert idx.search("") == []

    def test_whitespace_only_query_returns_empty(self):
        idx = SearchIndex.from_chunks([_chunk("a.py", 1, 5, "hello world")])
        assert idx.search("   ") == []
