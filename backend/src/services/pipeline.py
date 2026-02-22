"""Full wiki-generation pipeline.

Takes a raw GitHub repo URL and returns a fully-populated
:class:`~models.schemas.GenerateResponse`.

Pipeline stages
---------------
1.  **Parse** repo URL into ``owner`` and ``repo``.
2.  **Load snapshot** — fetch tree + file contents from GitHub.
3.  **Extract signals** — README headings, HTTP routes, entry points.
4.  **Chunk files** — split each file into line-numbered chunks.
5.  **Build import graph** — file-level dependency graph.
6.  **Build search index** — BM25 index over all chunks.
7.  **Propose features** — LLM call: 5–9 user-facing features.
8.  **Gather evidence** — bounded, deduped chunk packs per feature.
9.  **Write feature pages** — LLM call per feature with citations.
10. **Write overview** — LLM call using README + manifests.
11. **Assemble** :class:`~models.schemas.GenerateResponse`.

Debug mode
----------
When ``debug=True`` intermediate artifacts are printed to stdout as JSON
summaries (no secrets, no file contents — just stats and feature lists).
"""

from __future__ import annotations

import json
import re
from typing import Any

from models.schemas import GenerateResponse, WikiFeature
from services import chunker as chunker_mod
from services import import_graph as import_graph_mod
from services import repo_loader
from services.evidence import gather_all_evidence
from services.propose_features import propose_features
from services.search_index import SearchIndex
from services.signals import (
    RepoSignals,
    extract_entrypoints,
    extract_readme_signals,
    extract_route_signals,
)
from services.write_pages import write_all_feature_pages, write_overview_page

# ---------------------------------------------------------------------------
# Overview-file content retention set
# ---------------------------------------------------------------------------
# After chunking and building the import graph we no longer need the raw file
# content for most files.  We keep only README / manifest / entrypoint content
# because write_overview_page() reads it directly.
_OVERVIEW_KEEP_CONTENT: frozenset[str] = frozenset(
    {
        "readme.md",
        "readme.rst",
        "readme.txt",
        "readme",
        "package.json",
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "requirements.txt",
        "cargo.toml",
        "go.mod",
        "main.py",
        "__main__.py",
        "app.py",
        "server.py",
        "index.ts",
        "index.js",
        "index.tsx",
        "main.ts",
        "app.ts",
        "wsgi.py",
        "asgi.py",
    }
)


# ---------------------------------------------------------------------------
# URL parsing
# ---------------------------------------------------------------------------

_GITHUB_URL_RE = re.compile(
    r"https?://github\.com/([A-Za-z0-9_.\-]+)/([A-Za-z0-9_.\-]+?)(?:\.git)?/?$"
)


def _parse_owner_repo(repo_url: str) -> tuple[str, str]:
    """Extract (owner, repo) from a GitHub URL.

    Raises:
        ValueError: If the URL does not match the expected GitHub pattern.
    """
    m = _GITHUB_URL_RE.match(str(repo_url).rstrip("/"))
    if not m:
        raise ValueError(f"Cannot parse GitHub owner/repo from URL: {repo_url!r}")
    return m.group(1), m.group(2)


# ---------------------------------------------------------------------------
# Debug helpers
# ---------------------------------------------------------------------------


def _debug_print(label: str, payload: Any) -> None:
    print(f"\n[pipeline debug] {label}")
    try:
        print(json.dumps(payload, indent=2, default=str))
    except Exception:
        print(repr(payload))


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def run_pipeline(repo_url: str, *, debug: bool = False) -> GenerateResponse:
    """Run the full wiki-generation pipeline.

    Args:
        repo_url: Full GitHub URL, e.g. ``https://github.com/owner/repo``.
        debug:    When ``True``, print intermediate artifact summaries to
                  stdout.

    Returns:
        A fully-populated :class:`~models.schemas.GenerateResponse`.

    Raises:
        ValueError: If *repo_url* is not a valid GitHub URL.
    """
    owner, repo = _parse_owner_repo(repo_url)

    # ------------------------------------------------------------------
    # 1. Load snapshot
    # ------------------------------------------------------------------
    snapshot = repo_loader.load_snapshot(owner, repo)
    commit_sha = snapshot.commit_sha

    if debug:
        _debug_print(
            "snapshot",
            {
                "owner": owner,
                "repo": repo,
                "commit_sha": commit_sha,
                "file_count": len(snapshot.files),
                "files": [f.path for f in snapshot.files[:20]],
            },
        )

    # ------------------------------------------------------------------
    # 2. Extract signals
    # ------------------------------------------------------------------
    readme_headings = (
        extract_readme_signals(snapshot.readme.content) if snapshot.readme else []
    )
    routes = extract_route_signals(snapshot.files)
    entrypoints = extract_entrypoints(snapshot.files)
    signals = RepoSignals(
        readme_headings=readme_headings,
        routes=routes,
        entrypoints=entrypoints,
    )

    if debug:
        _debug_print(
            "signals",
            {
                "readme_headings": len(readme_headings),
                "routes": len(routes),
                "entrypoints": len(entrypoints),
            },
        )

    # ------------------------------------------------------------------
    # 3. Chunk all files
    # ------------------------------------------------------------------
    all_chunks = []
    for file_entry in snapshot.files:
        all_chunks.extend(chunker_mod.chunk_file(file_entry.path, file_entry.content))

    if debug:
        _debug_print(
            "chunks",
            {
                "total_chunks": len(all_chunks),
                "total_chars": sum(len(c.text) for c in all_chunks),
            },
        )

    # ------------------------------------------------------------------
    # 4. Build import graph
    # ------------------------------------------------------------------
    import_graph = import_graph_mod.build_import_graph(snapshot.files)

    if debug:
        _debug_print(
            "import_graph",
            {"edges": sum(len(v) for v in import_graph.values())},
        )

    # Free raw file content for non-overview files — chunks hold all the text
    # we need for the LLM stages, and keeping large source blobs in memory
    # through the LLM calls wastes RAM unnecessarily.
    for _fe in snapshot.files:
        if _fe.path.rsplit("/", 1)[-1].lower() not in _OVERVIEW_KEEP_CONTENT:
            _fe.content = ""

    # ------------------------------------------------------------------
    # 5. Build search index
    # ------------------------------------------------------------------
    search_index = SearchIndex()
    search_index.add_chunks(all_chunks)

    if debug:
        _debug_print("search_index", {"indexed_chunks": len(all_chunks)})

    # ------------------------------------------------------------------
    # 6. Propose features (LLM)
    # ------------------------------------------------------------------
    proposal_list = propose_features(snapshot, signals)
    features = proposal_list.features

    if debug:
        _debug_print(
            "features_proposed",
            {
                "count": len(features),
                "features": [
                    {"id": f.id, "title": f.title, "seed_paths": f.seed_paths}
                    for f in features
                ],
            },
        )

    # ------------------------------------------------------------------
    # 7. Gather evidence
    # ------------------------------------------------------------------
    packs = gather_all_evidence(features, all_chunks, import_graph, search_index)

    if debug:
        _debug_print(
            "evidence",
            {
                fid: {
                    "chunks": len(pack.chunks),
                    "chars": pack.total_chars,
                }
                for fid, pack in packs.items()
            },
        )

    # ------------------------------------------------------------------
    # 8. Write feature pages (LLM)
    # ------------------------------------------------------------------
    wiki_features: list[WikiFeature] = write_all_feature_pages(
        features, packs, owner=owner, repo=repo, commit_sha=commit_sha
    )

    # ------------------------------------------------------------------
    # 9. Write overview page (LLM)
    # ------------------------------------------------------------------
    overview_md = write_overview_page(
        snapshot, owner=owner, repo=repo, commit_sha=commit_sha
    )

    if debug:
        _debug_print(
            "output",
            {
                "overview_chars": len(overview_md),
                "feature_pages": len(wiki_features),
            },
        )

    # ------------------------------------------------------------------
    # 10. Assemble response
    # ------------------------------------------------------------------
    return GenerateResponse(
        repo_id=f"{owner}/{repo}",
        commit_sha=commit_sha,
        overview_md=overview_md,
        features=wiki_features,
    )
