import pytest
from fastapi.testclient import TestClient

import config
from main import app
from models.schemas import GenerateResponse

client = TestClient(app)

_TEST_KEY = "test-only-key"


@pytest.fixture(autouse=True)
def patch_api_key(monkeypatch):
    monkeypatch.setattr(config, "API_KEY", _TEST_KEY)


HEADERS = {"x-api-key": _TEST_KEY}


def test_response_matches_schema():
    body = {"repo_url": "https://github.com/owner/repo"}
    response = client.post("/api/generate", json=body, headers=HEADERS)
    assert response.status_code == 200
    # Validate against schema (raises ValidationError if fields missing/wrong type)
    data = GenerateResponse(**response.json())
    assert data.repo_id == "owner/repo"
    assert data.commit_sha
    assert data.overview_md
    assert len(data.features) >= 1


def test_response_repo_id_parsed_correctly():
    """owner/repo extracted correctly from various GitHub URL forms."""
    cases = [
        ("https://github.com/owner/repo", "owner/repo"),
        ("https://github.com/owner/repo/", "owner/repo"),
        ("https://github.com/owner/repo.git", "owner/repo"),
        # Repos whose names end in chars that rstrip(".git") would wrongly strip
        ("https://github.com/owner/light", "owner/light"),
        ("https://github.com/owner/digit", "owner/digit"),
    ]
    for url, expected_repo_id in cases:
        response = client.post("/api/generate", json={"repo_url": url}, headers=HEADERS)
        assert response.status_code == 200
        assert response.json()["repo_id"] == expected_repo_id


def test_feature_has_required_fields():
    body = {"repo_url": "https://github.com/owner/repo"}
    response = client.post("/api/generate", json=body, headers=HEADERS)
    features = response.json()["features"]
    assert len(features) >= 1
    for feature in features:
        assert "id" in feature
        assert "title" in feature
        assert "description" in feature
        assert "content_md" in feature
