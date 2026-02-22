"""Tests for services.citations — citation resolution to GitHub permalink links."""

from __future__ import annotations

import pytest

from services.citations import count_citations, resolve_citations

OWNER = "acme"
REPO = "myapp"
SHA = "abc1234def5678"


def _resolve(md: str) -> str:
    return resolve_citations(md, owner=OWNER, repo=REPO, commit_sha=SHA)


def _url(path: str, start: int, end: int) -> str:
    return f"https://github.com/{OWNER}/{REPO}/blob/{SHA}/{path}#L{start}-L{end}"


# ---------------------------------------------------------------------------
# Basic resolution
# ---------------------------------------------------------------------------


def test_simple_citation_resolved():
    md = "See the handler [src/auth.py:10-20] for details."
    result = _resolve(md)
    expected_link = f"[src/auth.py:10-20]({_url('src/auth.py', 10, 20)})"
    assert expected_link in result


def test_citation_with_nested_path():
    md = "Entry point: [backend/src/main.py:1-5]"
    result = _resolve(md)
    assert (
        f"(https://github.com/{OWNER}/{REPO}/blob/{SHA}/backend/src/main.py#L1-L5)"
        in result
    )


def test_citation_single_line_range():
    """Start and end line can be the same."""
    md = "The constant [config.py:42-42] sets the timeout."
    result = _resolve(md)
    assert f"[config.py:42-42]({_url('config.py', 42, 42)})" in result


def test_multiple_citations_in_document():
    md = "Auth is here [auth.py:1-10] and the model [models.py:20-30] wraps it."
    result = _resolve(md)
    assert f"[auth.py:1-10]({_url('auth.py', 1, 10)})" in result
    assert f"[models.py:20-30]({_url('models.py', 20, 30)})" in result


def test_citation_at_end_of_line():
    md = "See [utils.py:5-15]"
    result = _resolve(md)
    assert f"({_url('utils.py', 5, 15)})" in result


def test_citation_url_contains_correct_sha():
    md = "[a.py:1-1]"
    result = _resolve(md)
    assert SHA in result


def test_citation_url_contains_owner_and_repo():
    md = "[a.py:1-1]"
    result = _resolve(md)
    assert OWNER in result
    assert REPO in result


def test_citation_deep_path():
    """Paths with multiple slashes and dots are handled."""
    md = "[backend/src/services/auth/token.py:100-120]"
    result = _resolve(md)
    assert "backend/src/services/auth/token.py" in result
    assert "#L100-L120" in result


# ---------------------------------------------------------------------------
# Already-resolved citations are not double-resolved
# ---------------------------------------------------------------------------


def test_already_resolved_citation_left_intact():
    """A citation already followed by '(' (markdown link) must not be modified."""
    url = _url("a.py", 1, 5)
    md = f"[a.py:1-5]({url})"
    result = _resolve(md)
    # should remain exactly the same — one pair of parens, not two
    assert result == md
    assert result.count("(https://") == 1


def test_mix_resolved_and_unresolved():
    """Only unresolved citations are touched."""
    url = _url("a.py", 1, 5)
    md = f"already [a.py:1-5]({url}) and new [b.py:10-20]"
    result = _resolve(md)
    assert result.count("(https://") == 2
    assert f"[b.py:10-20]({_url('b.py', 10, 20)})" in result
    # original link unchanged
    assert f"[a.py:1-5]({url})" in result


# ---------------------------------------------------------------------------
# Invalid / edge-case citations are left intact
# ---------------------------------------------------------------------------


def test_citation_with_space_in_path_left_intact():
    """Paths containing spaces are invalid and left untouched."""
    md = "[path with spaces.py:1-10]"
    result = _resolve(md)
    assert result == md


def test_no_citations_document_unchanged():
    md = "This document has no citations whatsoever."
    assert _resolve(md) == md


def test_empty_string():
    assert _resolve("") == ""


def test_plain_markdown_link_untouched():
    """Regular markdown links [text](url) are not modified."""
    md = "[Click here](https://example.com) for more info."
    result = _resolve(md)
    assert result == md


def test_markdown_image_untouched():
    """Markdown images ![alt](url) are not modified."""
    md = "![diagram](https://example.com/img.png)"
    result = _resolve(md)
    assert result == md


def test_citation_without_line_range_not_treated_as_citation():
    """[path.py] without :start-end is not a citation."""
    md = "[some/path.py]"
    result = _resolve(md)
    assert result == md


# ---------------------------------------------------------------------------
# count_citations
# ---------------------------------------------------------------------------


def test_count_citations_zero():
    assert count_citations("No citations here.") == 0


def test_count_citations_one():
    assert count_citations("See [auth.py:1-10] for details.") == 1


def test_count_citations_multiple():
    md = "[a.py:1-5] and [b.py:10-20] and [c.py:30-40]"
    assert count_citations(md) == 3


def test_count_citations_already_resolved_not_counted():
    url = _url("a.py", 1, 5)
    md = f"[a.py:1-5]({url})"
    # already resolved — negative lookahead excludes it
    assert count_citations(md) == 0
