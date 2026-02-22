"""Smoke tests for services.pipeline.run_pipeline.

All external I/O is fully mocked:
  - services.repo_loader.load_snapshot → fake RepoSnapshot
  - OpenAI LLM client → injected mock via services.llm._set_client

No real GitHub or OpenAI calls are made.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from models.repo_snapshot import FileEntry, RepoSnapshot
from models.schemas import GenerateResponse, WikiFeature
from services.llm import _set_client
from services.pipeline import _parse_owner_repo, run_pipeline

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OWNER = "acme"
REPO = "widget"
SHA = "abc1234def5678"
REPO_URL = f"https://github.com/{OWNER}/{REPO}"


# ---------------------------------------------------------------------------
# Fake snapshot
# ---------------------------------------------------------------------------

_README_CONTENT = "# Widget\n\nWidget does cool things.\n\n## Getting Started\n\nRun `pip install widget`."
_MAIN_CONTENT = """\
from fastapi import FastAPI

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/widget")
def create_widget(name: str):
    return {"id": 1, "name": name}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
"""
_PYPROJECT_CONTENT = '[project]\nname = "widget"\nversion = "0.1.0"\n'

_FAKE_SNAPSHOT = RepoSnapshot(
    owner=OWNER,
    repo=REPO,
    default_branch="main",
    commit_sha=SHA,
    files=[
        FileEntry(path="README.md", size=len(_README_CONTENT), content=_README_CONTENT),
        FileEntry(path="main.py", size=len(_MAIN_CONTENT), content=_MAIN_CONTENT),
        FileEntry(path="pyproject.toml", size=len(_PYPROJECT_CONTENT), content=_PYPROJECT_CONTENT),
    ],
)

# ---------------------------------------------------------------------------
# LLM mock helpers
# ---------------------------------------------------------------------------


def _response(content: str):
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


_FEATURES_JSON = json.dumps(
    {
        "features": [
            {
                "id": "widget-creation",
                "title": "Widget Creation",
                "description": "Users can create and manage widgets via the API.",
                "seed_paths": ["main.py"],
            },
            {
                "id": "health-monitoring",
                "title": "Health Monitoring",
                "description": "Operators can check service health at any time.",
                "seed_paths": ["main.py"],
            },
        ]
    }
)
_FEATURE_PAGE_MD = "## Overview\n\nThis feature provides widget CRUD.\n\nSee [main.py:1-10]."
_OVERVIEW_MD = "## What\n\nWidget is a FastAPI app.\n\nSee [README.md:1-3]."


def _make_mock_client():
    """Return an LLM mock whose call sequence matches the pipeline stages.

    Call order:
    1. propose_features  → chat_json  → must return valid FeatureProposalList JSON
    2. write_feature_page (widget-creation) → chat_text → markdown
    3. write_feature_page (health-monitoring) → chat_text → markdown
    4. write_overview_page → chat_text → markdown
    """
    responses = [
        _response(_FEATURES_JSON),  # propose_features
        _response(_FEATURE_PAGE_MD),  # feature page 1
        _response(_FEATURE_PAGE_MD),  # feature page 2
        _response(_OVERVIEW_MD),  # overview
    ]
    client = MagicMock()
    client.chat.completions.create.side_effect = responses
    return client


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_llm_client():
    yield
    _set_client(None)


# ---------------------------------------------------------------------------
# _parse_owner_repo — unit tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://github.com/owner/repo", ("owner", "repo")),
        ("https://github.com/owner/repo/", ("owner", "repo")),
        ("https://github.com/owner/repo.git", ("owner", "repo")),
        ("https://www.github.com/org/my-project", None),  # www prefix not matched — invalid
        ("http://github.com/user/proj", ("user", "proj")),
        ("https://github.com/Meta-Inc/llama.cpp", ("Meta-Inc", "llama.cpp")),
    ],
)
def test_parse_owner_repo_parametrized(url, expected):
    if expected is None:
        with pytest.raises(ValueError):
            _parse_owner_repo(url)
    else:
        assert _parse_owner_repo(url) == expected


def test_parse_owner_repo_invalid_url_raises():
    with pytest.raises(ValueError, match="Cannot parse"):
        _parse_owner_repo("not-a-url")


def test_parse_owner_repo_non_github_raises():
    with pytest.raises(ValueError):
        _parse_owner_repo("https://gitlab.com/owner/repo")


# ---------------------------------------------------------------------------
# run_pipeline — return type and contract
# ---------------------------------------------------------------------------


def test_run_pipeline_returns_generate_response():
    _set_client(_make_mock_client())
    with patch("services.repo_loader.load_snapshot", return_value=_FAKE_SNAPSHOT):
        result = run_pipeline(REPO_URL)
    assert isinstance(result, GenerateResponse)


def test_run_pipeline_repo_id_correct():
    _set_client(_make_mock_client())
    with patch("services.repo_loader.load_snapshot", return_value=_FAKE_SNAPSHOT):
        result = run_pipeline(REPO_URL)
    assert result.repo_id == f"{OWNER}/{REPO}"


def test_run_pipeline_commit_sha_correct():
    _set_client(_make_mock_client())
    with patch("services.repo_loader.load_snapshot", return_value=_FAKE_SNAPSHOT):
        result = run_pipeline(REPO_URL)
    assert result.commit_sha == SHA


def test_run_pipeline_overview_md_populated():
    _set_client(_make_mock_client())
    with patch("services.repo_loader.load_snapshot", return_value=_FAKE_SNAPSHOT):
        result = run_pipeline(REPO_URL)
    assert isinstance(result.overview_md, str)
    assert len(result.overview_md) > 0


def test_run_pipeline_features_is_list():
    _set_client(_make_mock_client())
    with patch("services.repo_loader.load_snapshot", return_value=_FAKE_SNAPSHOT):
        result = run_pipeline(REPO_URL)
    assert isinstance(result.features, list)


def test_run_pipeline_features_count():
    """Pipeline produces one WikiFeature per proposed feature (2 in our mock)."""
    _set_client(_make_mock_client())
    with patch("services.repo_loader.load_snapshot", return_value=_FAKE_SNAPSHOT):
        result = run_pipeline(REPO_URL)
    assert len(result.features) == 2


def test_run_pipeline_features_are_wiki_feature_instances():
    _set_client(_make_mock_client())
    with patch("services.repo_loader.load_snapshot", return_value=_FAKE_SNAPSHOT):
        result = run_pipeline(REPO_URL)
    for feat in result.features:
        assert isinstance(feat, WikiFeature)


def test_run_pipeline_feature_ids():
    _set_client(_make_mock_client())
    with patch("services.repo_loader.load_snapshot", return_value=_FAKE_SNAPSHOT):
        result = run_pipeline(REPO_URL)
    ids = {f.id for f in result.features}
    assert "widget-creation" in ids
    assert "health-monitoring" in ids


def test_run_pipeline_feature_content_md_populated():
    _set_client(_make_mock_client())
    with patch("services.repo_loader.load_snapshot", return_value=_FAKE_SNAPSHOT):
        result = run_pipeline(REPO_URL)
    for feat in result.features:
        assert isinstance(feat.content_md, str)
        assert len(feat.content_md) > 0


def test_run_pipeline_citations_resolved_in_features():
    """Citations like [main.py:1-10] should be resolved to GitHub permalink URLs."""
    _set_client(_make_mock_client())
    with patch("services.repo_loader.load_snapshot", return_value=_FAKE_SNAPSHOT):
        result = run_pipeline(REPO_URL)
    # At least one feature page should have a resolved citation
    all_content = " ".join(f.content_md for f in result.features)
    assert f"https://github.com/{OWNER}/{REPO}/blob/{SHA}/" in all_content


def test_run_pipeline_citations_resolved_in_overview():
    """Citations in overview_md should be resolved to GitHub permalink URLs."""
    _set_client(_make_mock_client())
    with patch("services.repo_loader.load_snapshot", return_value=_FAKE_SNAPSHOT):
        result = run_pipeline(REPO_URL)
    assert f"https://github.com/{OWNER}/{REPO}/blob/{SHA}/" in result.overview_md


def test_run_pipeline_invalid_url_raises_value_error():
    with pytest.raises(ValueError):
        run_pipeline("not-a-github-url")


def test_run_pipeline_no_real_network_calls(monkeypatch):
    """Pipeline must not make real network calls with mocked snapshot + LLM."""
    _set_client(_make_mock_client())

    import httpx

    def _no_network(*args, **kwargs):
        raise AssertionError("No real network calls should be made in smoke tests")

    monkeypatch.setattr(httpx, "get", _no_network)

    with patch("services.repo_loader.load_snapshot", return_value=_FAKE_SNAPSHOT):
        result = run_pipeline(REPO_URL)

    assert isinstance(result, GenerateResponse)
