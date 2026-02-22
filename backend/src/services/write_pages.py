"""Generate per-feature wiki pages and the repo-level overview page using the LLM.

Each feature page is a markdown document with:
- A brief user-facing description of what the feature does
- How the feature works (drawing from evidence chunks)
- Key interfaces, entry points, or public API surface
- Inline citations in ``[path:start-end]`` format

The overview page covers what the repo does, its high-level architecture,
and how to run it, drawing from the README, manifest files, and main entry
points.

After the LLM generates raw markdown the internal citations are resolved
to stable GitHub permalink links via :mod:`services.citations`.
"""

from __future__ import annotations

from models.llm_schemas import FeatureProposal
from models.repo_snapshot import FileEntry, RepoSnapshot
from models.schemas import WikiFeature
from services.citations import resolve_citations
from services.evidence import EvidencePack
from services import llm

# ---------------------------------------------------------------------------
# Prompt constants
# ---------------------------------------------------------------------------

_SYSTEM = """\
You are a senior technical writer producing developer documentation for a \
software repository wiki.

Your task is to write a clear, well-structured wiki page for a single \
user-facing feature.  The page is aimed at developers who want to understand \
how the feature works and where to find the relevant code.

Guidelines:
1. Target audience: engineers reading the docs, not end users.
2. Structure: start with a 1-2 sentence overview, then explain how the \
feature is implemented, then list key entry points / public interfaces.
3. Cite every non-trivial claim using the chunk citation format: \
[path/to/file.ext:start_line-end_line].  Use the EXACT chunk IDs provided.
4. Write in plain markdown.  Use ## for section headings.  No title heading \
(it is added separately).
5. Do NOT invent file paths or line numbers.  Only cite chunk IDs you can \
see in the evidence below.
6. Do NOT include a table of contents.
7. Keep the page concise: 200-600 words of prose, supplemented by citations.
"""

# Maximum characters of chunk text to include in the prompt per chunk.
# Evidence is already bounded by gather_evidence(); this is a per-chunk
# display cap to avoid runaway individual files dominating the prompt.
_CHUNK_DISPLAY_CHARS = 1_500


def _format_evidence(pack: EvidencePack) -> str:
    """Render evidence chunks as a structured block for the LLM prompt."""
    parts: list[str] = []
    for chunk in pack.chunks:
        text = chunk.text
        if len(text) > _CHUNK_DISPLAY_CHARS:
            text = text[:_CHUNK_DISPLAY_CHARS] + "\n... [truncated]"
        parts.append(f"=== [{chunk.chunk_id}] ===\n{text}")
    return "\n\n".join(parts)


def write_feature_page(
    feature: FeatureProposal,
    pack: EvidencePack,
    owner: str,
    repo: str,
    commit_sha: str,
) -> WikiFeature:
    """Generate a markdown wiki page for *feature* from its evidence pack.

    Args:
        feature:    The :class:`~models.llm_schemas.FeatureProposal` to
                    document.
        pack:       :class:`~services.evidence.EvidencePack` with supporting
                    code evidence.
        owner:      GitHub repository owner.
        repo:       GitHub repository name.
        commit_sha: Commit SHA used to build stable citation URLs.

    Returns:
        A populated :class:`~models.schemas.WikiFeature` with
        ``content_md`` containing resolved GitHub permalink citations.
    """
    evidence_text = _format_evidence(pack)

    user_prompt = (
        f"Feature title: {feature.title}\n"
        f"Feature description: {feature.description}\n\n"
        "Evidence chunks (use [chunk_id] citations for claims):\n\n"
        f"{evidence_text}"
    )

    raw_md = llm.chat_text(_SYSTEM, user_prompt)
    resolved_md = resolve_citations(
        raw_md, owner=owner, repo=repo, commit_sha=commit_sha
    )

    return WikiFeature(
        id=feature.id,
        title=feature.title,
        description=feature.description,
        content_md=resolved_md,
    )


def write_all_feature_pages(
    features: list[FeatureProposal],
    packs: dict[str, EvidencePack],
    owner: str,
    repo: str,
    commit_sha: str,
) -> list[WikiFeature]:
    """Write pages for all features in order.

    Args:
        features:   All proposed features (order is preserved in output).
        packs:      Mapping of ``feature_id → EvidencePack``.
        owner:      GitHub repository owner.
        repo:       GitHub repository name.
        commit_sha: Commit SHA for citation link generation.

    Returns:
        List of :class:`~models.schemas.WikiFeature` in the same order as
        *features*.
    """
    pages: list[WikiFeature] = []
    for feature in features:
        pack = packs.get(feature.id)
        if pack is None:
            # Shouldn't happen in normal flow; produce a stub page rather than crash.
            pack = EvidencePack(feature_id=feature.id, chunks=[])
        pages.append(
            write_feature_page(
                feature, pack, owner=owner, repo=repo, commit_sha=commit_sha
            )
        )
    return pages


# ---------------------------------------------------------------------------
# Overview page
# ---------------------------------------------------------------------------

# Filenames (case-insensitive, final path component) that are included in
# the overview evidence.
_README_NAMES: frozenset[str] = frozenset(
    {"readme.md", "readme.rst", "readme.txt", "readme"}
)
_MANIFEST_NAMES: frozenset[str] = frozenset(
    {"package.json", "pyproject.toml", "setup.py", "cargo.toml", "go.mod"}
)
_ENTRYPOINT_NAMES: frozenset[str] = frozenset(
    {
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

# Per-file character display cap inside the overview prompt — keeps the
# context focused and bounded.
_OVERVIEW_FILE_MAX_CHARS: int = 3_000

_OVERVIEW_SYSTEM = """\
You are a senior technical writer creating the overview page for a software \
repository wiki.

Write a concise, developer-facing overview in plain markdown covering:
1. **What this project does** — a 2-3 sentence summary for engineers.
2. **High-level architecture** — key components and how they relate.
3. **How to run / get started** — installation and quickstart steps if \
evident from the files.

Guidelines:
- Target audience: engineers, not end users.
- Use ## for section headings.  Do NOT add a title heading.
- Cite every nontrivial claim using the chunk citation format: \
[path/to/file.ext:start_line-end_line].  Only cite files shown below.
- Do NOT invent file paths or line numbers.
- Keep to 200-500 words of prose.
"""


def _is_overview_file(path: str) -> bool:
    """Return ``True`` if *path* should be included in the overview evidence."""
    fname = path.rsplit("/", 1)[-1].lower()
    return fname in _README_NAMES or fname in _MANIFEST_NAMES or fname in _ENTRYPOINT_NAMES


def _gather_overview_files(snapshot: RepoSnapshot) -> list[FileEntry]:
    """Select README, manifest and entrypoint files from *snapshot*."""
    return [f for f in snapshot.files if _is_overview_file(f.path)]


def write_overview_page(
    snapshot: RepoSnapshot,
    owner: str,
    repo: str,
    commit_sha: str,
) -> str:
    """Generate a repo-level overview using the LLM.

    The evidence set is intentionally small — README, package manifests, and
    main entry-point files — so the overview stays high-level rather than
    drowning in implementation details.

    Args:
        snapshot:   Full :class:`~models.repo_snapshot.RepoSnapshot` for the
                    repository.
        owner:      GitHub repository owner.
        repo:       GitHub repository name.
        commit_sha: Commit SHA used for stable citation permalink URLs.

    Returns:
        Resolved markdown string for the overview page.
    """
    files = _gather_overview_files(snapshot)

    parts: list[str] = []
    for f in files:
        text = f.content
        if len(text) > _OVERVIEW_FILE_MAX_CHARS:
            text = text[:_OVERVIEW_FILE_MAX_CHARS] + "\n... [truncated]"
        parts.append(f"=== {f.path} ===\n{text}")

    evidence_block = "\n\n".join(parts) if parts else "(no overview files found)"

    user_prompt = (
        f"Repository: {owner}/{repo}\n\n"
        "Files (cite using [path:start_line-end_line]):\n\n"
        f"{evidence_block}"
    )

    raw_md = llm.chat_text(_OVERVIEW_SYSTEM, user_prompt)
    return resolve_citations(raw_md, owner=owner, repo=repo, commit_sha=commit_sha)
