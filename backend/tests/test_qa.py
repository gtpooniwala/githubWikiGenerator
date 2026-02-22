"""Tests for the POST /api/qa endpoint."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import config
from main import app
from routers.qa import _build_user_message
from models.schemas import QARequest, WikiFeature

client = TestClient(app)
VALID_KEY = "test-key"

SAMPLE_FEATURES = [
    WikiFeature(
        id="auth",
        title="User Authentication",
        description="Handles sign-up, login, and session management.",
        content_md="## How it works\n\nJWT tokens issued on login [auth.py:10-30].",
    ),
    WikiFeature(
        id="search",
        title="Search & Discovery",
        description="Full-text search over all content.",
        content_md="## Implementation\n\nBM25 index built on startup [search.py:1-50].",
    ),
]

SAMPLE_REQUEST_BODY = {
    "repo_id": "owner/repo",
    "question": "How does authentication work?",
    "overview_md": "## Overview\n\nThis repo is a demo app.",
    "features": [f.model_dump() for f in SAMPLE_FEATURES],
}


@pytest.fixture(autouse=True)
def patch_api_key(monkeypatch):
    monkeypatch.setattr(config, "API_KEY", VALID_KEY)


# ---------------------------------------------------------------------------
# Auth checks
# ---------------------------------------------------------------------------


def test_qa_missing_api_key():
    response = client.post("/api/qa", json=SAMPLE_REQUEST_BODY)
    assert response.status_code == 401


def test_qa_wrong_api_key():
    response = client.post(
        "/api/qa",
        json=SAMPLE_REQUEST_BODY,
        headers={"x-api-key": "wrong-key"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_qa_returns_answer():
    with patch(
        "routers.qa.llm.chat_text", return_value="Auth uses JWT tokens."
    ) as mock_chat:
        response = client.post(
            "/api/qa",
            json=SAMPLE_REQUEST_BODY,
            headers={"x-api-key": VALID_KEY},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Auth uses JWT tokens."
    mock_chat.assert_called_once()


def test_qa_passes_correct_system_and_user_message():
    """Verify the LLM receives the system prompt and a user message containing
    the wiki context and the question."""
    captured: dict = {}

    def fake_chat_text(system: str, user: str, **kwargs) -> str:
        captured["system"] = system
        captured["user"] = user
        return "mocked answer"

    with patch("routers.qa.llm.chat_text", side_effect=fake_chat_text):
        client.post(
            "/api/qa",
            json=SAMPLE_REQUEST_BODY,
            headers={"x-api-key": VALID_KEY},
        )

    # System prompt should mention wiki documentation
    assert "wiki" in captured["system"].lower()
    # User message should include the repo ID
    assert "owner/repo" in captured["user"]
    # User message should include the question
    assert "How does authentication work?" in captured["user"]
    # User message should include overview content
    assert "demo app" in captured["user"]
    # User message should include feature content
    assert "User Authentication" in captured["user"]
    assert "Search & Discovery" in captured["user"]


def test_qa_with_no_features():
    body = {
        "repo_id": "owner/minimal",
        "question": "What does this do?",
        "overview_md": "A minimal project.",
        "features": [],
    }
    with patch("routers.qa.llm.chat_text", return_value="It is a minimal project."):
        response = client.post(
            "/api/qa",
            json=body,
            headers={"x-api-key": VALID_KEY},
        )
    assert response.status_code == 200
    assert response.json()["answer"] == "It is a minimal project."


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_qa_empty_question_returns_422():
    body = {**SAMPLE_REQUEST_BODY, "question": "   "}
    response = client.post("/api/qa", json=body, headers={"x-api-key": VALID_KEY})
    assert response.status_code == 422


def test_qa_missing_question_field_returns_422():
    body = {k: v for k, v in SAMPLE_REQUEST_BODY.items() if k != "question"}
    response = client.post("/api/qa", json=body, headers={"x-api-key": VALID_KEY})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# LLM error propagation
# ---------------------------------------------------------------------------


def test_qa_llm_error_returns_502():
    import openai

    with patch(
        "routers.qa.llm.chat_text",
        side_effect=openai.APIConnectionError(request=None),  # type: ignore[arg-type]
    ):
        response = client.post(
            "/api/qa",
            json=SAMPLE_REQUEST_BODY,
            headers={"x-api-key": VALID_KEY},
        )
    assert response.status_code == 502


# ---------------------------------------------------------------------------
# Context builder unit tests
# ---------------------------------------------------------------------------


def test_build_user_message_contains_all_sections():
    request = QARequest(
        repo_id="owner/repo",
        question="What search algorithm is used?",
        overview_md="## Overview\n\nDemo app.",
        features=SAMPLE_FEATURES,
    )
    msg = _build_user_message(request)

    assert "owner/repo" in msg
    assert "Demo app." in msg
    assert "User Authentication" in msg
    assert "Search & Discovery" in msg
    assert "BM25 index" in msg
    assert "What search algorithm is used?" in msg


def test_build_user_message_includes_feature_description():
    request = QARequest(
        repo_id="owner/repo",
        question="Q?",
        overview_md="Overview.",
        features=SAMPLE_FEATURES,
    )
    msg = _build_user_message(request)
    assert "Handles sign-up, login, and session management." in msg


def test_build_user_message_truncates_very_large_wiki():
    huge_overview = "x" * 90_000
    request = QARequest(
        repo_id="owner/repo",
        question="Q?",
        overview_md=huge_overview,
        features=[],
    )
    msg = _build_user_message(request)
    assert "truncated" in msg
    # The total message should be bounded (some extra chars for question/header)
    assert len(msg) < 90_000
