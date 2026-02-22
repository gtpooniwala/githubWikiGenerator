import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

VALID_KEY = "dev-key-123"
GENERATE_URL = "/api/generate?repo_url=https://github.com/owner/repo"


def test_missing_key_returns_401():
    response = client.post(GENERATE_URL)
    assert response.status_code == 401


def test_wrong_key_returns_401():
    response = client.post(GENERATE_URL, headers={"x-api-key": "wrong-key"})
    assert response.status_code == 401


def test_correct_key_returns_200():
    response = client.post(GENERATE_URL, headers={"x-api-key": VALID_KEY})
    assert response.status_code == 200


def test_auth_error_is_json():
    response = client.post(GENERATE_URL)
    assert response.headers["content-type"].startswith("application/json")
    assert "detail" in response.json()
