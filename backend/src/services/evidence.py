"""Assemble bounded, deduplicated evidence packs for each feature proposal.

Pipeline per feature
--------------------
1. Collect all chunks from ``seed_paths``.
2. Expand via import graph up to ``max_hops`` hops (BFS).
3. Add top-k search hits from the keyword index (title + description query).
4. Deduplicate by chunk_id (seed / expanded chunks have priority).
5. Enforce ``max_chunks`` and ``max_chars`` limits.

Usage::

    pack = gather_evidence(
        feature,
        all_chunks=all_chunks,
        import_graph=import_graph,
        search_index=search_index,
    )
    # pack.chunks is a deterministically-ordered list[Chunk]
"""

from __future__ import annotations

from dataclasses import dataclass, field

from models.llm_schemas import FeatureProposal
from services.chunker import Chunk
from services.search_index import SearchIndex

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_MAX_HOPS: int = 2
DEFAULT_MAX_CHUNKS: int = 40
DEFAULT_MAX_CHARS: int = 80_000
_SEARCH_K: int = 20  # search hits requested per feature


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass
class EvidencePack:
    """A bounded, deduplicated collection of chunks for one feature."""

    feature_id: str
    chunks: list[Chunk] = field(default_factory=list)

    @property
    def total_chars(self) -> int:
        """Total character count across all included chunks."""
        return sum(len(c.text) for c in self.chunks)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _expand_via_import_graph(
    seed_paths: set[str],
    import_graph: dict[str, list[str]],
    max_hops: int,
) -> set[str]:
    """Return all paths reachable from *seed_paths* within *max_hops* hops.

    The import graph maps ``path → [imported_path, ...]``.  We perform a BFS
    and include the seed paths themselves in the returned set.
    """
    visited: set[str] = set(seed_paths)
    frontier: set[str] = set(seed_paths)
    for _ in range(max_hops):
        next_frontier: set[str] = set()
        for path in frontier:
            for dep in import_graph.get(path, []):
                if dep not in visited:
                    visited.add(dep)
                    next_frontier.add(dep)
        frontier = next_frontier
        if not frontier:
            break
    return visited


def _feature_query(feature: FeatureProposal) -> str:
    """Build a keyword query string from a feature's title and description."""
    return f"{feature.title} {feature.description}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def gather_evidence(
    feature: FeatureProposal,
    all_chunks: list[Chunk],
    import_graph: dict[str, list[str]],
    search_index: SearchIndex,
    *,
    max_hops: int = DEFAULT_MAX_HOPS,
    max_chunks: int = DEFAULT_MAX_CHUNKS,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> EvidencePack:
    """Return a bounded, deduplicated :class:`EvidencePack` for *feature*.

    Args:
        feature:      The :class:`~models.llm_schemas.FeatureProposal` to
                      gather evidence for.
        all_chunks:   Every chunk produced by the chunker for the snapshot.
        import_graph: File-level import graph from
                      :func:`~services.import_graph.build_import_graph`.
        search_index: Pre-built :class:`~services.search_index.SearchIndex`.
        max_hops:     Maximum BFS depth for import graph expansion.
        max_chunks:   Hard cap on the number of chunks returned.
        max_chars:    Hard cap on the total character count of returned chunks.

    Returns:
        An :class:`EvidencePack` with ``chunks`` ordered seed-first, then
        alphabetically by path and start line for determinism.
    """
    seed_paths: set[str] = set(feature.seed_paths)

    # ------------------------------------------------------------------
    # 1. Build a path → chunks lookup
    # ------------------------------------------------------------------
    chunks_by_path: dict[str, list[Chunk]] = {}
    for chunk in all_chunks:
        chunks_by_path.setdefault(chunk.path, []).append(chunk)

    # ------------------------------------------------------------------
    # 2. Expand seed paths via import graph
    # ------------------------------------------------------------------
    expanded_paths = _expand_via_import_graph(seed_paths, import_graph, max_hops)

    # ------------------------------------------------------------------
    # 3. Collect seed + expanded chunks (preserve insertion order via dict)
    # ------------------------------------------------------------------
    # chunk_id → (is_seed_file, Chunk)  — used for priority sorting later
    collected: dict[str, tuple[bool, Chunk]] = {}

    for path in sorted(expanded_paths):  # sorted for determinism
        is_seed = path in seed_paths
        for chunk in chunks_by_path.get(path, []):
            if chunk.chunk_id not in collected:
                collected[chunk.chunk_id] = (is_seed, chunk)

    # ------------------------------------------------------------------
    # 4. Add search hits not already collected
    # ------------------------------------------------------------------
    query = _feature_query(feature)
    results = search_index.search(query, k=_SEARCH_K)
    for result in results:
        if result.chunk_id not in collected:
            for chunk in chunks_by_path.get(result.path, []):
                if chunk.chunk_id == result.chunk_id:
                    collected[chunk.chunk_id] = (False, chunk)
                    break

    # ------------------------------------------------------------------
    # 5. Sort: seed-file chunks first, then (path, start_line) for determinism
    # ------------------------------------------------------------------
    def _sort_key(item: tuple[str, tuple[bool, Chunk]]) -> tuple[int, str, int]:
        _cid, (is_seed, chunk) = item
        return (0 if is_seed else 1, chunk.path, chunk.start_line)

    ordered_chunks = [chunk for _, (_, chunk) in sorted(collected.items(), key=_sort_key)]

    # ------------------------------------------------------------------
    # 6. Enforce bounds
    # ------------------------------------------------------------------
    result: list[Chunk] = []
    total_chars = 0
    for chunk in ordered_chunks:
        if len(result) >= max_chunks:
            break
        if total_chars + len(chunk.text) > max_chars:
            break
        result.append(chunk)
        total_chars += len(chunk.text)

    return EvidencePack(feature_id=feature.id, chunks=result)


def gather_all_evidence(
    features: list[FeatureProposal],
    all_chunks: list[Chunk],
    import_graph: dict[str, list[str]],
    search_index: SearchIndex,
    *,
    max_hops: int = DEFAULT_MAX_HOPS,
    max_chunks: int = DEFAULT_MAX_CHUNKS,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> dict[str, EvidencePack]:
    """Convenience wrapper: gather evidence for every feature in *features*.

    Returns a mapping of ``feature_id → EvidencePack``.
    """
    return {
        f.id: gather_evidence(
            f,
            all_chunks=all_chunks,
            import_graph=import_graph,
            search_index=search_index,
            max_hops=max_hops,
            max_chunks=max_chunks,
            max_chars=max_chars,
        )
        for f in features
    }
