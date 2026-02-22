"""Propose 5–9 user-facing features for a repository using the LLM.

The LLM is given:
  - Repo name + commit
  - README headings
  - Discovered HTTP routes
  - Entry-point scripts
  - A trimmed file list

It returns a :class:`~models.llm_schemas.FeatureProposalList` where each
feature has a URL-safe ``id`` slug, a ``title``, a ``description``, and
``seed_paths`` pointing to the most relevant files.
"""

from __future__ import annotations

import re

from models.llm_schemas import FeatureProposal, FeatureProposalList
from models.repo_snapshot import RepoSnapshot
from services import llm
from services.signals import RepoSignals

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Titles containing these words describe technical layers, not user features.
BANNED_TITLE_WORDS: frozenset[str] = frozenset(
    {
        "utils",
        "util",
        "helpers",
        "helper",
        "components",
        "component",
        "frontend",
        "backend",
        "middleware",
        "infrastructure",
        "config",
        "configuration",
        "misc",
        "miscellaneous",
        "common",
        "shared",
    }
)

_SLUG_RE = re.compile(r"[^a-z0-9]+")

_MAX_HEADINGS = 25
_MAX_ROUTES = 30
_MAX_FILES = 100

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM = """\
You are a senior technical writer analysing a software repository.
Your task is to identify 5–9 USER-FACING FEATURES – the distinct things
the software lets users *do* or *experience*.

Rules:
1. Every title must describe what a user gains or accomplishes.
   Good: "User Authentication", "Real-time Notifications", "Search & Discovery"
   Bad: "Frontend", "Backend", "Utils", "Helpers", "Components", "Middleware"
2. Do NOT use the following words in any title (case-insensitive):
   utils, util, helpers, helper, components, component, frontend, backend,
   middleware, infrastructure, config, configuration, misc, shared, common.
3. Output exactly a JSON object matching this schema:
   {
     "features": [
       {
         "id": "<url-safe-slug>",
         "title": "<user-facing title>",
         "description": "<1-3 sentences describing what the user can do>",
         "seed_paths": ["<repo-relative file path>", ...]
       }
     ]
   }
4. seed_paths should list the 2–6 files most central to implementing the feature.
5. Produce between 5 and 9 features. Do not produce more or fewer.
"""


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------


def _build_context(snapshot: RepoSnapshot, signals: RepoSignals) -> str:
    """Assemble a concise text summary of the repo to pass as the user message."""
    lines: list[str] = []

    lines.append(f"Repository: {snapshot.owner}/{snapshot.repo}")
    lines.append(f"Default branch: {snapshot.default_branch}")
    lines.append(f"Commit: {snapshot.commit_sha[:7]}")
    lines.append("")

    if signals.readme_headings:
        lines.append("## README headings")
        for h in signals.readme_headings[:_MAX_HEADINGS]:
            lines.append(f"{'#' * h.level} {h.text}")
        lines.append("")

    if signals.routes:
        lines.append("## HTTP routes")
        for r in signals.routes[:_MAX_ROUTES]:
            lines.append(f"  {r.method} {r.path}  ({r.file_path}:{r.line_no})")
        lines.append("")

    if signals.entrypoints:
        lines.append("## Entry points")
        for ep in signals.entrypoints:
            lines.append(f"  [{ep.kind}] {ep.name}: {ep.command}")
        lines.append("")

    lines.append("## Files")
    for f in snapshot.files[:_MAX_FILES]:
        lines.append(f"  {f.path}")
    if len(snapshot.files) > _MAX_FILES:
        lines.append(f"  ... and {len(snapshot.files) - _MAX_FILES} more files")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Slug normalisation
# ---------------------------------------------------------------------------


def _slugify(text: str) -> str:
    """Convert *text* to a URL-safe lowercase slug."""
    return _SLUG_RE.sub("-", text.lower()).strip("-")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def propose_features(
    snapshot: RepoSnapshot, signals: RepoSignals
) -> FeatureProposalList:
    """Call the LLM to propose 5–9 user-facing features for the repository.

    Args:
        snapshot: The loaded :class:`RepoSnapshot`.
        signals:  Pre-extracted :class:`RepoSignals`.

    Returns:
        A validated :class:`FeatureProposalList` with normalised slugs and
        any banned-title features removed.

    Raises:
        ValueError: If the LLM response is not valid JSON or does not match
                    the expected schema.
    """
    context = _build_context(snapshot, signals)
    result: FeatureProposalList = llm.chat_json(_SYSTEM, context, FeatureProposalList)

    # Post-process: normalise slugs and strip features whose title contains
    # a banned word (in case the LLM ignored the instruction).
    clean: list[FeatureProposal] = []
    for feat in result.features:
        title_lower = feat.title.lower()
        if any(word in title_lower for word in BANNED_TITLE_WORDS):
            continue
        slug = _slugify(feat.id) or _slugify(feat.title)
        clean.append(
            FeatureProposal(
                id=slug,
                title=feat.title,
                description=feat.description,
                seed_paths=feat.seed_paths,
            )
        )

    return FeatureProposalList(features=clean)
