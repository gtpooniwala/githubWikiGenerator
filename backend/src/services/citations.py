"""Convert internal chunk citations to GitHub permalink markdown links.

LLM-generated pages use the internal citation format::

    [path/to/file.py:10-20]

This module resolves those to stable GitHub blob URLs anchored to the
exact commit SHA analysed::

    [path/to/file.py:10-20](https://github.com/owner/repo/blob/<sha>/path/to/file.py#L10-L20)

Invalid citations (non-integer line numbers, empty path) are left untouched
so they surface clearly during review rather than silently disappearing.
"""

from __future__ import annotations

import re

# Matches: [some/path/file.ext:start-end]
# - path may contain letters, digits, /, ., _, -, @
# - start and end are integers
# - must NOT match standard markdown links like [text](url) — those already
#   have a parenthesised dest and are not touched
_CITATION_RE = re.compile(
    r"""
    \[                           # opening bracket
    ([^\[\]\n]+?)                # group 1: path (non-greedy, no newlines)
    :                            # colon separator
    (\d+)                        # group 2: start line
    -                            # dash
    (\d+)                        # group 3: end line
    \]                           # closing bracket
    (?!\()                       # negative lookahead: must NOT be followed by '('
                                 # (would indicate an already-resolved link)
    """,
    re.VERBOSE,
)

_GITHUB_BLOB = "https://github.com/{owner}/{repo}/blob/{sha}/{path}#L{start}-L{end}"


def resolve_citations(
    markdown: str,
    owner: str,
    repo: str,
    commit_sha: str,
) -> str:
    """Replace all ``[path:start-end]`` citations with GitHub permalink links.

    Args:
        markdown:   Raw markdown text containing internal citations.
        owner:      GitHub repository owner (user or org).
        repo:       GitHub repository name.
        commit_sha: The commit SHA the analysis was performed against.

    Returns:
        Markdown with citations replaced by ``[path:start-end](github_url)``
        links.  Citations that are already resolved (followed by ``(``) are
        left intact.  Citations with invalid structure are left intact.
    """

    def _replace(m: re.Match) -> str:
        path = m.group(1).strip()
        start = m.group(2)
        end = m.group(3)

        # Sanity: path must be non-empty and not contain spaces
        if not path or " " in path:
            return m.group(0)  # leave unchanged

        url = _GITHUB_BLOB.format(
            owner=owner,
            repo=repo,
            sha=commit_sha,
            path=path,
            start=start,
            end=end,
        )
        return f"[{path}:{start}-{end}]({url})"

    return _CITATION_RE.sub(_replace, markdown)


def count_citations(markdown: str) -> int:
    """Return the number of unresolved ``[path:start-end]`` citations in *markdown*."""
    return len(_CITATION_RE.findall(markdown))
