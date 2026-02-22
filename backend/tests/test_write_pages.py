"""Tests for services.write_pages — LLM feature page generation.

All tests are fully isolated — no real OpenAI calls are made.
The ``_set_client`` escape-hatch from services.llm is used to inject mocks.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, call

import pytest

from models.llm_schemas import FeatureProposal
from models.schemas import WikiFeature
from services.chunker import Chunk
from services.evidence import EvidencePack
from services.llm import _set_client
from services.write_pages import (
    _CHUNK_DISPLAY_CHARS,
    _OVERVIEW_FILE_MAX_CHARS,
    write_all_feature_pages,
    write_feature_page,
    write_overview_page,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

OWNER = "acme"
REPO = "myapp"
SHA = "deadbeef1234"


def _make_response(content: str):
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


def _mock_client(content: str) -> MagicMock:
    client = MagicMock()
    client.chat.completions.create.return_value = _make_response(content)
    return client


def _chunk(path: str, start: int, end: int, text: str = "code here") -> Chunk:
    return Chunk(
        chunk_id=f"{path}:{start}-{end}",
        path=path,
        start_line=start,
        end_line=end,
        text=text,
    )


def _feature(
    fid: str = "auth",
    title: str = "User Authentication",
    description: str = "Handles login and sessions.",
    seed_paths: list[str] | None = None,
) -> FeatureProposal:
    return FeatureProposal(
        id=fid,
        title=title,
        description=description,
        seed_paths=seed_paths or [],
    )


def _pack(feature_id: str, chunks: list[Chunk]) -> EvidencePack:
    return EvidencePack(feature_id=feature_id, chunks=chunks)


@pytest.fixture(autouse=True)
def reset_llm_client():
    """Always reset the LLM client after each test."""
    yield
    _set_client(None)


# ---------------------------------------------------------------------------
# write_feature_page — return type and field values
# ---------------------------------------------------------------------------


def test_returns_wiki_feature():
    _set_client(_mock_client("## Overview\nThis handles auth [auth.py:1-10]."))
    feat = _feature()
    pack = _pack("auth", [_chunk("auth.py", 1, 10)])
    result = write_feature_page(feat, pack, OWNER, REPO, SHA)
    assert isinstance(result, WikiFeature)


def test_feature_id_preserved():
    _set_client(_mock_client("Some content."))
    feat = _feature(fid="my-feature")
    pack = _pack("my-feature", [])
    result = write_feature_page(feat, pack, OWNER, REPO, SHA)
    assert result.id == "my-feature"


def test_feature_title_preserved():
    _set_client(_mock_client("Content here."))
    feat = _feature(title="User Sign-in")
    pack = _pack("auth", [])
    result = write_feature_page(feat, pack, OWNER, REPO, SHA)
    assert result.title == "User Sign-in"


def test_feature_description_preserved():
    _set_client(_mock_client("Content here."))
    feat = _feature(description="Secure login flow.")
    pack = _pack("auth", [])
    result = write_feature_page(feat, pack, OWNER, REPO, SHA)
    assert result.description == "Secure login flow."


# ---------------------------------------------------------------------------
# write_feature_page — citations are resolved in content_md
# ---------------------------------------------------------------------------


def test_citations_resolved_in_content_md():
    """[path:start-end] citations in LLM output are converted to GH links."""
    _set_client(_mock_client("Auth is in [auth.py:1-10] and [models.py:5-15]."))
    feat = _feature()
    pack = _pack("auth", [_chunk("auth.py", 1, 10), _chunk("models.py", 5, 15)])
    result = write_feature_page(feat, pack, OWNER, REPO, SHA)
    assert (
        f"https://github.com/{OWNER}/{REPO}/blob/{SHA}/auth.py#L1-L10"
        in result.content_md
    )
    assert (
        f"https://github.com/{OWNER}/{REPO}/blob/{SHA}/models.py#L5-L15"
        in result.content_md
    )


def test_content_md_with_no_citations_returned_as_is():
    raw = "This feature provides user authentication with no citations."
    _set_client(_mock_client(raw))
    feat = _feature()
    pack = _pack("auth", [])
    result = write_feature_page(feat, pack, OWNER, REPO, SHA)
    assert result.content_md == raw


def test_sha_used_in_citation_urls():
    _set_client(_mock_client("See [a.py:1-1]."))
    feat = _feature()
    pack = _pack("auth", [_chunk("a.py", 1, 1)])
    result = write_feature_page(feat, pack, OWNER, REPO, SHA)
    assert SHA in result.content_md


# ---------------------------------------------------------------------------
# write_feature_page — prompt contains feature info + chunk IDs
# ---------------------------------------------------------------------------


def test_prompt_contains_feature_title():
    mock = _mock_client("OK.")
    _set_client(mock)
    feat = _feature(title="Search & Discovery")
    pack = _pack("search", [])
    write_feature_page(feat, pack, OWNER, REPO, SHA)
    call_args = mock.chat.completions.create.call_args
    messages = call_args.kwargs["messages"]
    user_content = next(m["content"] for m in messages if m["role"] == "user")
    assert "Search & Discovery" in user_content


def test_prompt_contains_feature_description():
    mock = _mock_client("OK.")
    _set_client(mock)
    feat = _feature(description="Allows full-text search across all items.")
    pack = _pack("search", [])
    write_feature_page(feat, pack, OWNER, REPO, SHA)
    call_args = mock.chat.completions.create.call_args
    messages = call_args.kwargs["messages"]
    user_content = next(m["content"] for m in messages if m["role"] == "user")
    assert "Allows full-text search across all items." in user_content


def test_prompt_contains_chunk_ids():
    mock = _mock_client("Page content.")
    _set_client(mock)
    feat = _feature()
    c1 = _chunk("auth.py", 1, 10)
    c2 = _chunk("session.py", 5, 20)
    pack = _pack("auth", [c1, c2])
    write_feature_page(feat, pack, OWNER, REPO, SHA)
    call_args = mock.chat.completions.create.call_args
    messages = call_args.kwargs["messages"]
    user_content = next(m["content"] for m in messages if m["role"] == "user")
    assert "auth.py:1-10" in user_content
    assert "session.py:5-20" in user_content


def test_prompt_contains_chunk_text():
    mock = _mock_client("Page content.")
    _set_client(mock)
    feat = _feature()
    c = _chunk("auth.py", 1, 5, text="def login(user, pwd): ...")
    pack = _pack("auth", [c])
    write_feature_page(feat, pack, OWNER, REPO, SHA)
    call_args = mock.chat.completions.create.call_args
    messages = call_args.kwargs["messages"]
    user_content = next(m["content"] for m in messages if m["role"] == "user")
    assert "def login(user, pwd)" in user_content


def test_long_chunk_text_truncated_in_prompt():
    """Chunk text exceeding _CHUNK_DISPLAY_CHARS is truncated in the prompt."""
    long_text = "x" * (_CHUNK_DISPLAY_CHARS + 500)
    mock = _mock_client("OK.")
    _set_client(mock)
    feat = _feature()
    c = _chunk("big.py", 1, 1000, text=long_text)
    pack = _pack("auth", [c])
    write_feature_page(feat, pack, OWNER, REPO, SHA)
    call_args = mock.chat.completions.create.call_args
    messages = call_args.kwargs["messages"]
    user_content = next(m["content"] for m in messages if m["role"] == "user")
    assert "truncated" in user_content
    # Full text must not appear
    assert long_text not in user_content


def test_empty_evidence_pack_no_crash():
    _set_client(_mock_client("No evidence available for this feature."))
    feat = _feature()
    pack = _pack("auth", [])
    result = write_feature_page(feat, pack, OWNER, REPO, SHA)
    assert isinstance(result, WikiFeature)
    assert result.id == "auth"


# ---------------------------------------------------------------------------
# write_all_feature_pages
# ---------------------------------------------------------------------------


def test_write_all_feature_pages_returns_list():
    _set_client(_mock_client("Content."))
    f1 = _feature(fid="f1", title="Feature One")
    f2 = _feature(fid="f2", title="Feature Two")
    packs = {
        "f1": _pack("f1", []),
        "f2": _pack("f2", []),
    }
    result = write_all_feature_pages([f1, f2], packs, OWNER, REPO, SHA)
    assert isinstance(result, list)
    assert len(result) == 2


def test_write_all_feature_pages_order_preserved():
    _set_client(_mock_client("Content."))
    f1 = _feature(fid="alpha", title="Alpha")
    f2 = _feature(fid="beta", title="Beta")
    f3 = _feature(fid="gamma", title="Gamma")
    packs = {fid: _pack(fid, []) for fid in ["alpha", "beta", "gamma"]}
    result = write_all_feature_pages([f1, f2, f3], packs, OWNER, REPO, SHA)
    assert [r.id for r in result] == ["alpha", "beta", "gamma"]


def test_write_all_feature_pages_calls_llm_per_feature():
    mock = _mock_client("Content.")
    _set_client(mock)
    f1 = _feature(fid="f1")
    f2 = _feature(fid="f2")
    packs = {"f1": _pack("f1", []), "f2": _pack("f2", [])}
    write_all_feature_pages([f1, f2], packs, OWNER, REPO, SHA)
    assert mock.chat.completions.create.call_count == 2


def test_write_all_feature_pages_missing_pack_no_crash():
    """A feature with no pack in the dict degrades gracefully."""
    _set_client(_mock_client("Fallback content."))
    feat = _feature(fid="unknown")
    result = write_all_feature_pages([feat], {}, OWNER, REPO, SHA)
    assert len(result) == 1
    assert result[0].id == "unknown"


def test_write_all_feature_pages_empty_features_returns_empty():
    _set_client(_mock_client("Content."))
    result = write_all_feature_pages([], {}, OWNER, REPO, SHA)
    assert result == []


# ---------------------------------------------------------------------------
# write_overview_page helpers
# ---------------------------------------------------------------------------

import pytest as _pytest  # noqa: E402 — local alias to avoid re-import confusion

from models.repo_snapshot import FileEntry, RepoSnapshot


def _snapshot(files: list[FileEntry] | None = None) -> RepoSnapshot:
    return RepoSnapshot(
        owner=OWNER,
        repo=REPO,
        default_branch="main",
        commit_sha=SHA,
        files=files or [],
    )


def _file(path: str, content: str) -> FileEntry:
    return FileEntry(path=path, size=len(content), content=content)


# ---------------------------------------------------------------------------
# write_overview_page — basic contract
# ---------------------------------------------------------------------------


def test_overview_returns_string():
    _set_client(_mock_client("## What\nThis project does X."))
    snap = _snapshot()
    result = write_overview_page(snap, OWNER, REPO, SHA)
    assert isinstance(result, str)
    assert len(result) > 0


def test_overview_citations_resolved():
    """Citations in the LLM output are converted to GitHub permalink links."""
    _set_client(_mock_client("Entry point at [main.py:1-5]."))
    snap = _snapshot([_file("main.py", "# main\n")])
    result = write_overview_page(snap, OWNER, REPO, SHA)
    assert f"https://github.com/{OWNER}/{REPO}/blob/{SHA}/main.py#L1-L5" in result


def test_overview_sha_in_citation_url():
    _set_client(_mock_client("Config in [config.py:10-20]."))
    snap = _snapshot([_file("config.py", "# cfg\n")])
    result = write_overview_page(snap, OWNER, REPO, SHA)
    assert SHA in result


def test_overview_no_citations_returned_as_is():
    raw = "An overview with no citations."
    _set_client(_mock_client(raw))
    snap = _snapshot()
    result = write_overview_page(snap, OWNER, REPO, SHA)
    assert result == raw


def test_overview_empty_snapshot_no_crash():
    _set_client(_mock_client("Overview text."))
    snap = _snapshot([])
    result = write_overview_page(snap, OWNER, REPO, SHA)
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# write_overview_page — evidence selection
# ---------------------------------------------------------------------------


def test_overview_prompt_contains_readme_content():
    mock = _mock_client("Overview.")
    _set_client(mock)
    snap = _snapshot([_file("README.md", "# MyApp\nDoes amazing things.")])
    write_overview_page(snap, OWNER, REPO, SHA)
    call_args = mock.chat.completions.create.call_args
    messages = call_args.kwargs["messages"]
    user_content = next(m["content"] for m in messages if m["role"] == "user")
    assert "Does amazing things." in user_content


def test_overview_prompt_contains_package_json():
    mock = _mock_client("Overview.")
    _set_client(mock)
    snap = _snapshot([_file("package.json", '{"name":"myapp","scripts":{"start":"node index.js"}}')])
    write_overview_page(snap, OWNER, REPO, SHA)
    call_args = mock.chat.completions.create.call_args
    messages = call_args.kwargs["messages"]
    user_content = next(m["content"] for m in messages if m["role"] == "user")
    assert "package.json" in user_content
    assert "myapp" in user_content


def test_overview_prompt_contains_pyproject_toml():
    mock = _mock_client("Overview.")
    _set_client(mock)
    snap = _snapshot([_file("pyproject.toml", '[project]\nname = "myapp"\n')])
    write_overview_page(snap, OWNER, REPO, SHA)
    call_args = mock.chat.completions.create.call_args
    messages = call_args.kwargs["messages"]
    user_content = next(m["content"] for m in messages if m["role"] == "user")
    assert "pyproject.toml" in user_content


def test_overview_prompt_contains_entrypoint():
    mock = _mock_client("Overview.")
    _set_client(mock)
    snap = _snapshot([_file("main.py", "if __name__ == '__main__': run()")])
    write_overview_page(snap, OWNER, REPO, SHA)
    call_args = mock.chat.completions.create.call_args
    messages = call_args.kwargs["messages"]
    user_content = next(m["content"] for m in messages if m["role"] == "user")
    assert "main.py" in user_content
    assert "run()" in user_content


def test_overview_non_overview_files_excluded():
    """Implementation files not in the evidence set should not appear in prompt."""
    mock = _mock_client("Overview.")
    _set_client(mock)
    snap = _snapshot([
        _file("README.md", "Docs."),
        _file("src/utils/helpers.py", "def helper(): pass"),
        _file("src/db/models.py", "class User: pass"),
    ])
    write_overview_page(snap, OWNER, REPO, SHA)
    call_args = mock.chat.completions.create.call_args
    messages = call_args.kwargs["messages"]
    user_content = next(m["content"] for m in messages if m["role"] == "user")
    assert "helpers.py" not in user_content
    assert "models.py" not in user_content


def test_overview_long_file_truncated_in_prompt():
    """Files exceeding _OVERVIEW_FILE_MAX_CHARS are truncated."""
    long_content = "x" * (_OVERVIEW_FILE_MAX_CHARS + 500)
    mock = _mock_client("Overview.")
    _set_client(mock)
    snap = _snapshot([_file("README.md", long_content)])
    write_overview_page(snap, OWNER, REPO, SHA)
    call_args = mock.chat.completions.create.call_args
    messages = call_args.kwargs["messages"]
    user_content = next(m["content"] for m in messages if m["role"] == "user")
    assert "truncated" in user_content
    assert long_content not in user_content


def test_overview_prompt_contains_owner_repo():
    mock = _mock_client("Overview.")
    _set_client(mock)
    snap = _snapshot()
    write_overview_page(snap, OWNER, REPO, SHA)
    call_args = mock.chat.completions.create.call_args
    messages = call_args.kwargs["messages"]
    user_content = next(m["content"] for m in messages if m["role"] == "user")
    assert f"{OWNER}/{REPO}" in user_content


def test_overview_nested_entrypoint_included():
    """Entrypoint files in subdirectories are still included."""
    mock = _mock_client("Overview.")
    _set_client(mock)
    snap = _snapshot([_file("src/app.py", "from fastapi import FastAPI\napp = FastAPI()")])
    write_overview_page(snap, OWNER, REPO, SHA)
    call_args = mock.chat.completions.create.call_args
    messages = call_args.kwargs["messages"]
    user_content = next(m["content"] for m in messages if m["role"] == "user")
    assert "src/app.py" in user_content
