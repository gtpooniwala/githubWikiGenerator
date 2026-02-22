from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import config
from main import app
from models.schemas import GenerateResponse, WikiFeature

GENERATE_URL = "/api/generate"
VALID_BODY = {"repo_url": "https://github.com/owner/repo"}
# Test key — an arbitrary value used only within this test suite.
# config.API_KEY is monkeypatched to this value so tests are self-consistent
# without relying on any real credential.
_TEST_KEY = "test-only-key"


@pytest.fixture(autouse=True)
def patch_api_key(monkeypatch):
    monkeypatch.setattr(config, "API_KEY", _TEST_KEY)


_STUB_RESPONSE = GenerateResponse(
    repo_id="owner/repo",
    commit_sha="stub-sha",
    overview_md="Overview.",
    features=[
        WikiFeature(
            id="f1",
            title="Feature One",
            description="Desc.",
            content_md="Content.",
        )
    ],
)


@pytest.fixture(autouse=True)
def patch_pipeline():
    with patch("routers.generate.run_pipeline", return_value=_STUB_RESPONSE):
        yield


client = TestClient(app)


def test_missing_key_returns_401():
    response = client.post(GENERATE_URL, json=VALID_BODY)
    assert response.status_code == 401


def test_wrong_key_returns_401():
    response = client.post(
        GENERATE_URL, json=VALID_BODY, headers={"x-api-key": "wrong-key"}
    )
    assert response.status_code == 401


def test_correct_key_returns_200():
    response = client.post(
        GENERATE_URL, json=VALID_BODY, headers={"x-api-key": _TEST_KEY}
    )
    assert response.status_code == 200


def test_auth_error_is_json():
    response = client.post(GENERATE_URL, json=VALID_BODY)
    assert response.headers["content-type"].startswith("application/json")
    assert "detail" in response.json()
