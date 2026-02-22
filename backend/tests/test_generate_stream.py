"""Tests for the real-pipeline SSE /api/generate/stream endpoint."""
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import config
from main import app

client = TestClient(app)
VALID_KEY = "test-key"
REPO_URL = "https://github.com/owner/repo"


@pytest.fixture(autouse=True)
def patch_api_key(monkeypatch):
    monkeypatch.setattr(config, "API_KEY", VALID_KEY)


def _make_snapshot(commit_sha: str = "abc123", file_count: int = 3):
    snapshot = MagicMock()
    snapshot.commit_sha = commit_sha
    snapshot.files = [
        MagicMock(path=f"file{i}.py", content=f"def fn_{i}(): pass", size=20)
        for i in range(file_count)
    ]
    return snapshot


@pytest.fixture()
def mock_pipeline():
    snapshot = _make_snapshot()
    with (
        patch("routers.generate.load_snapshot", return_value=snapshot) as mock_load,
        patch("routers.generate.chunk_file", return_value=[MagicMock()]) as mock_chunk,
        patch("routers.generate.extract_readme_signals", return_value=[]),
        patch("routers.generate.extract_route_signals", return_value=[]),
        patch("routers.generate.extract_entrypoints", return_value=[]),
    ):
        yield {"snapshot": snapshot, "load_snapshot": mock_load, "chunk_file": mock_chunk}


# ---------------------------------------------------------------------------
# Auth / validation
# ---------------------------------------------------------------------------

def test_stream_missing_auth():
    r = client.get("/api/generate/stream", params={"repo_url": REPO_URL})
    assert r.status_code == 401


def test_stream_wrong_auth():
    r = client.get("/api/generate/stream", params={"repo_url": REPO_URL}, headers={"x-api-key": "wrong"})
    assert r.status_code == 401


def test_stream_missing_repo_url():
    r = client.get("/api/generate/stream", headers={"x-api-key": VALID_KEY})
    assert r.status_code == 422  # FastAPI query-param validation


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------

def test_stream_returns_event_stream_content_type(mock_pipeline):
    r = client.get("/api/generate/stream", params={"repo_url": REPO_URL}, headers={"x-api-key": VALID_KEY})
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]


def test_stream_emits_all_expected_events(mock_pipeline):
    r = client.get("/api/generate/stream", params={"repo_url": REPO_URL}, headers={"x-api-key": VALID_KEY})
    text = r.text
    for event_name in ["repo_loaded", "chunked", "signals_extracted", "features_proposed", "pages_written", "done"]:
        assert f"event: {event_name}" in text, f"Missing event: {event_name}"


def test_stream_event_blocks_have_valid_json_data(mock_pipeline):
    r = client.get("/api/generate/stream", params={"repo_url": REPO_URL}, headers={"x-api-key": VALID_KEY})
    blocks = [b for b in r.text.strip().split("\n\n") if b.strip()]
    assert len(blocks) == 6
    for block in blocks:
        lines = [l for l in block.splitlines() if l.strip()]
        assert any(l.startswith("event:") for l in lines)
        data_lines = [l for l in lines if l.startswith("data:")]
        assert data_lines
        payload = json.loads(data_lines[0].removeprefix("data:").strip())
        assert "message" in payload


def test_stream_repo_loaded_includes_metadata(mock_pipeline):
    r = client.get("/api/generate/stream", params={"repo_url": REPO_URL}, headers={"x-api-key": VALID_KEY})
    blocks = [b for b in r.text.strip().split("\n\n") if b.strip()]
    block = next(b for b in blocks if "event: repo_loaded" in b)
    data = json.loads(block.split("data:")[1].strip())
    assert data["file_count"] == 3
    assert data["commit_sha"] == "abc123"


def test_stream_chunked_includes_chunk_count(mock_pipeline):
    # 3 files × 1 chunk each = 3 chunks
    r = client.get("/api/generate/stream", params={"repo_url": REPO_URL}, headers={"x-api-key": VALID_KEY})
    blocks = [b for b in r.text.strip().split("\n\n") if b.strip()]
    block = next(b for b in blocks if "event: chunked" in b)
    data = json.loads(block.split("data:")[1].strip())
    assert data["chunk_count"] == 3


def test_stream_done_is_last_event(mock_pipeline):
    r = client.get("/api/generate/stream", params={"repo_url": REPO_URL}, headers={"x-api-key": VALID_KEY})
    blocks = [b for b in r.text.strip().split("\n\n") if b.strip()]
    assert "event: done" in blocks[-1]


def test_stream_calls_real_services(mock_pipeline):
    client.get("/api/generate/stream", params={"repo_url": REPO_URL}, headers={"x-api-key": VALID_KEY})
    mock_pipeline["load_snapshot"].assert_called_once_with("owner", "repo")
    assert mock_pipeline["chunk_file"].call_count == 3  # once per file
