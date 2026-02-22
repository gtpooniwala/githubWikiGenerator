"""Tests for services.evidence — evidence pack gathering."""

from __future__ import annotations

import pytest

from models.llm_schemas import FeatureProposal
from services.chunker import Chunk
from services.evidence import (
    DEFAULT_MAX_CHARS,
    DEFAULT_MAX_CHUNKS,
    DEFAULT_MAX_HOPS,
    EvidencePack,
    gather_all_evidence,
    gather_evidence,
)
from services.search_index import SearchIndex


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _chunk(path: str, start: int, end: int, text: str = "") -> Chunk:
    if not text:
        text = f"content of {path}:{start}-{end}"
    return Chunk(
        chunk_id=f"{path}:{start}-{end}",
        path=path,
        start_line=start,
        end_line=end,
        text=text,
    )


def _feature(
    fid: str = "feat",
    title: str = "My Feature",
    description: str = "does things",
    seed_paths: list[str] | None = None,
) -> FeatureProposal:
    return FeatureProposal(
        id=fid,
        title=title,
        description=description,
        seed_paths=seed_paths or [],
    )


def _index(chunks: list[Chunk]) -> SearchIndex:
    return SearchIndex.from_chunks(chunks)


# ---------------------------------------------------------------------------
# seed_paths → chunks included
# ---------------------------------------------------------------------------


def test_seed_chunks_included():
    """All chunks from seed_paths appear in the evidence pack."""
    c1 = _chunk("auth.py", 1, 10)
    c2 = _chunk("auth.py", 11, 20)
    c3 = _chunk("other.py", 1, 10)
    feat = _feature(seed_paths=["auth.py"])
    pack = gather_evidence(feat, [c1, c2, c3], {}, _index([c1, c2, c3]))
    ids = {c.chunk_id for c in pack.chunks}
    assert f"auth.py:1-10" in ids
    assert f"auth.py:11-20" in ids


def test_non_seed_non_imported_non_matching_excluded():
    """Chunks from unrelated paths that have no keyword overlap are excluded."""
    seed = _chunk("login.py", 1, 10, "login authentication token")
    unrelated = _chunk("styles.py", 1, 10, "xyzzy_no_match_word_at_all_here")
    feat = _feature(seed_paths=["login.py"])
    pack = gather_evidence(feat, [seed, unrelated], {}, _index([seed, unrelated]))
    ids = {c.chunk_id for c in pack.chunks}
    assert "login.py:1-10" in ids
    assert "styles.py:1-10" not in ids


def test_unknown_seed_path_silently_ignored():
    """A seed path that has no chunks in the corpus is silently ignored."""
    c = _chunk("real.py", 1, 5)
    feat = _feature(seed_paths=["missing.py"])
    pack = gather_evidence(feat, [c], {}, _index([c]))
    # should not raise; pack may be empty or contain search hits only
    assert isinstance(pack.chunks, list)


# ---------------------------------------------------------------------------
# Import graph expansion
# ---------------------------------------------------------------------------


def test_import_graph_one_hop():
    """Chunks from files 1 hop away from seeds are included."""
    seed_chunk = _chunk("app.py", 1, 5)
    dep_chunk = _chunk("db.py", 1, 5)
    graph = {"app.py": ["db.py"]}
    feat = _feature(seed_paths=["app.py"])
    pack = gather_evidence(feat, [seed_chunk, dep_chunk], graph, _index([seed_chunk, dep_chunk]))
    ids = {c.chunk_id for c in pack.chunks}
    assert "app.py:1-5" in ids
    assert "db.py:1-5" in ids


def test_import_graph_two_hops():
    """Chunks reachable in exactly 2 hops are included with default max_hops=2."""
    a = _chunk("a.py", 1, 5)
    b = _chunk("b.py", 1, 5)
    c = _chunk("c.py", 1, 5)
    graph = {"a.py": ["b.py"], "b.py": ["c.py"]}
    feat = _feature(seed_paths=["a.py"])
    pack = gather_evidence(feat, [a, b, c], graph, _index([a, b, c]))
    ids = {c.chunk_id for c in pack.chunks}
    assert "a.py:1-5" in ids
    assert "b.py:1-5" in ids
    assert "c.py:1-5" in ids


def test_import_graph_max_hops_zero_no_expansion():
    """max_hops=0 means only seed files are directly collected; no expansion."""
    seed = _chunk("a.py", 1, 5)
    dep = _chunk("b.py", 1, 5)
    graph = {"a.py": ["b.py"]}
    feat = _feature(seed_paths=["a.py"])
    pack = gather_evidence(feat, [seed, dep], graph, _index([seed, dep]), max_hops=0)
    ids = {c.chunk_id for c in pack.chunks}
    assert "a.py:1-5" in ids
    assert "b.py:1-5" not in ids


def test_import_graph_max_hops_one_excludes_two_hop_paths():
    """max_hops=1 includes 1-hop deps but not 2-hop deps."""
    a = _chunk("a.py", 1, 5)
    b = _chunk("b.py", 1, 5)
    c = _chunk("c.py", 1, 5)
    graph = {"a.py": ["b.py"], "b.py": ["c.py"]}
    feat = _feature(seed_paths=["a.py"])
    pack = gather_evidence(feat, [a, b, c], graph, _index([a, b, c]), max_hops=1)
    ids = {c.chunk_id for c in pack.chunks}
    assert "b.py:1-5" in ids
    assert "c.py:1-5" not in ids


def test_cyclic_import_graph_does_not_loop():
    """Cyclic imports (a→b→a) terminate without error."""
    a = _chunk("a.py", 1, 5)
    b = _chunk("b.py", 1, 5)
    graph = {"a.py": ["b.py"], "b.py": ["a.py"]}
    feat = _feature(seed_paths=["a.py"])
    pack = gather_evidence(feat, [a, b], graph, _index([a, b]))
    assert len(pack.chunks) == 2


# ---------------------------------------------------------------------------
# Search hits
# ---------------------------------------------------------------------------


def test_search_hits_included():
    """Chunks that match the keyword query but are not in seed paths are added."""
    seed = _chunk("api.py", 1, 5, "route definition")
    hit = _chunk("utils.py", 1, 5, "route definition helper")
    feat = _feature(title="Route", description="route definition")
    pack = gather_evidence(feat, [seed, hit], {}, _index([seed, hit]))
    ids = {c.chunk_id for c in pack.chunks}
    assert "utils.py:1-5" in ids


def test_search_hit_not_duplicated_when_in_seed():
    """A chunk that is both a seed chunk and a search hit appears only once."""
    c = _chunk("auth.py", 1, 10, "authentication login")
    feat = _feature(title="Authentication", description="login", seed_paths=["auth.py"])
    pack = gather_evidence(feat, [c], {}, _index([c]))
    count = sum(1 for chunk in pack.chunks if chunk.chunk_id == "auth.py:1-10")
    assert count == 1


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def test_deduplication_across_expansion_and_search():
    """A chunk reachable via both import expansion and search appears once."""
    seed = _chunk("a.py", 1, 5, "feature keyword")
    dep = _chunk("b.py", 1, 5, "feature keyword")  # also a search hit
    graph = {"a.py": ["b.py"]}
    feat = _feature(title="Feature keyword", description="something", seed_paths=["a.py"])
    pack = gather_evidence(feat, [seed, dep], graph, _index([seed, dep]))
    ids = [c.chunk_id for c in pack.chunks]
    assert ids.count("b.py:1-5") == 1


# ---------------------------------------------------------------------------
# Bounds
# ---------------------------------------------------------------------------


def test_max_chunks_bound_respected():
    """The number of chunks never exceeds max_chunks."""
    chunks = [_chunk("f.py", i, i + 1, "auth login") for i in range(1, 21)]
    feat = _feature(seed_paths=["f.py"])
    pack = gather_evidence(feat, chunks, {}, _index(chunks), max_chunks=5)
    assert len(pack.chunks) <= 5


def test_max_chars_bound_respected():
    """total_chars never exceeds max_chars."""
    # each chunk has ~50 chars
    chunks = [_chunk("f.py", i, i + 1, "x" * 50) for i in range(1, 21)]
    feat = _feature(seed_paths=["f.py"])
    pack = gather_evidence(feat, chunks, {}, _index(chunks), max_chars=200)
    assert pack.total_chars <= 200


def test_seed_chunks_prioritised_when_max_chunks_exceeded():
    """When max_chunks is tight, seed-file chunks come before expanded/search chunks."""
    seed_chunks = [_chunk("seed.py", i, i + 1) for i in range(1, 6)]
    other_chunks = [_chunk("other.py", i, i + 1) for i in range(1, 6)]
    graph = {"seed.py": ["other.py"]}
    feat = _feature(seed_paths=["seed.py"])
    all_chunks = seed_chunks + other_chunks
    pack = gather_evidence(feat, all_chunks, graph, _index(all_chunks), max_chunks=5)
    assert len(pack.chunks) == 5
    # all retained chunks must be from seed.py
    assert all(c.path == "seed.py" for c in pack.chunks)


def test_max_chunks_zero_returns_empty():
    """max_chunks=0 returns an empty pack."""
    c = _chunk("a.py", 1, 5)
    feat = _feature(seed_paths=["a.py"])
    pack = gather_evidence(feat, [c], {}, _index([c]), max_chunks=0)
    assert pack.chunks == []


def test_max_chars_zero_returns_empty():
    """max_chars=0 prevents any chunk from being added."""
    c = _chunk("a.py", 1, 5)
    feat = _feature(seed_paths=["a.py"])
    pack = gather_evidence(feat, [c], {}, _index([c]), max_chars=0)
    assert pack.chunks == []


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_corpus_returns_empty_pack():
    """When there are no chunks at all, the pack is empty."""
    feat = _feature(seed_paths=["a.py"])
    pack = gather_evidence(feat, [], {}, _index([]))
    assert pack.chunks == []
    assert pack.total_chars == 0


def test_empty_seed_paths_uses_search_only():
    """With no seed paths, evidence is drawn solely from search hits."""
    c = _chunk("utils.py", 1, 10, "authentication login user")
    feat = _feature(title="Authentication", description="login", seed_paths=[])
    pack = gather_evidence(feat, [c], {}, _index([c]))
    ids = {ch.chunk_id for ch in pack.chunks}
    assert "utils.py:1-10" in ids


# ---------------------------------------------------------------------------
# EvidencePack properties
# ---------------------------------------------------------------------------


def test_evidence_pack_feature_id():
    feat = _feature(fid="my-feature", seed_paths=["a.py"])
    c = _chunk("a.py", 1, 5)
    pack = gather_evidence(feat, [c], {}, _index([c]))
    assert pack.feature_id == "my-feature"


def test_evidence_pack_total_chars():
    c1 = _chunk("a.py", 1, 5, "hello")   # 5 chars
    c2 = _chunk("a.py", 6, 10, "world1")  # 6 chars
    feat = _feature(seed_paths=["a.py"])
    pack = gather_evidence(feat, [c1, c2], {}, _index([c1, c2]))
    assert pack.total_chars == 11


def test_default_constants():
    """Sanity-check the advertised default values."""
    assert DEFAULT_MAX_HOPS == 2
    assert DEFAULT_MAX_CHUNKS == 40
    assert DEFAULT_MAX_CHARS == 80_000


# ---------------------------------------------------------------------------
# gather_all_evidence convenience wrapper
# ---------------------------------------------------------------------------


def test_gather_all_evidence_returns_dict_keyed_by_feature_id():
    c1 = _chunk("a.py", 1, 5)
    c2 = _chunk("b.py", 1, 5)
    f1 = _feature(fid="feat-a", seed_paths=["a.py"])
    f2 = _feature(fid="feat-b", seed_paths=["b.py"])
    result = gather_all_evidence([f1, f2], [c1, c2], {}, _index([c1, c2]))
    assert set(result.keys()) == {"feat-a", "feat-b"}
    assert isinstance(result["feat-a"], EvidencePack)
    assert isinstance(result["feat-b"], EvidencePack)


def test_gather_all_evidence_packs_are_independent():
    """Evidence packs for different features don't share chunks incorrectly."""
    c_a = _chunk("a.py", 1, 5, "alpha")
    c_b = _chunk("b.py", 1, 5, "beta")
    f1 = _feature(fid="alpha-feat", title="Alpha", description="alpha stuff", seed_paths=["a.py"])
    f2 = _feature(fid="beta-feat", title="Beta", description="beta stuff", seed_paths=["b.py"])
    result = gather_all_evidence([f1, f2], [c_a, c_b], {}, _index([c_a, c_b]))
    assert "a.py:1-5" in {c.chunk_id for c in result["alpha-feat"].chunks}
    assert "b.py:1-5" in {c.chunk_id for c in result["beta-feat"].chunks}


def test_gather_all_evidence_empty_features_list():
    result = gather_all_evidence([], [], {}, _index([]))
    assert result == {}
