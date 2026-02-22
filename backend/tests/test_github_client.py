import json
from pathlib import Path

import pytest
import respx
import httpx

from services import github_client

FIXTURES = Path(__file__).parent / "fixtures" / "github_api"
OWNER = "owner"
REPO = "sample-repo"
SHA = "abc123def456abc123def456abc123def456abc1"


@pytest.fixture
def mock_github():
    """Activate respx router for all tests in this module."""
    with respx.mock(base_url="https://api.github.com", assert_all_called=False) as router:
        # GET /repos/owner/sample-repo
        router.get(f"/repos/{OWNER}/{REPO}").mock(
            return_value=httpx.Response(200, json=json.loads((FIXTURES / "repo.json").read_text()))
        )
        # GET /repos/owner/sample-repo/git/ref/heads/main
        router.get(f"/repos/{OWNER}/{REPO}/git/ref/heads/main").mock(
            return_value=httpx.Response(200, json=json.loads((FIXTURES / "ref.json").read_text()))
        )
        # GET /repos/owner/sample-repo/git/trees/<sha>
        router.get(f"/repos/{OWNER}/{REPO}/git/trees/{SHA}").mock(
            return_value=httpx.Response(200, json=json.loads((FIXTURES / "tree.json").read_text()))
        )
        # GET /repos/owner/sample-repo/contents/README.md
        router.get(f"/repos/{OWNER}/{REPO}/contents/README.md").mock(
            return_value=httpx.Response(200, json=json.loads((FIXTURES / "readme_file.json").read_text()))
        )
        # Generic stub for any other content file
        router.get(url__regex=f"/repos/{OWNER}/{REPO}/contents/.*").mock(
            return_value=httpx.Response(200, json={
                "encoding": "base64",
                "content": "cHJpbnQoJ2hlbGxvJyk=",  # print('hello')
            })
        )
        yield router


def test_get_repo(mock_github):
    data = github_client.get_repo(OWNER, REPO)
    assert data["default_branch"] == "main"
    assert data["name"] == "sample-repo"


def test_get_branch_sha(mock_github):
    sha = github_client.get_branch_sha(OWNER, REPO, "main")
    assert sha == SHA


def test_get_tree(mock_github):
    tree = github_client.get_tree(OWNER, REPO, SHA)
    paths = [item["path"] for item in tree]
    assert "README.md" in paths
    assert "main.py" in paths


def test_get_file_decodes_base64(mock_github):
    content = github_client.get_file(OWNER, REPO, "README.md", SHA)
    assert "Sample Repo" in content
