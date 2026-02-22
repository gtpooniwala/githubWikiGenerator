import json
from pathlib import Path

import pytest
import respx
import httpx

from services.repo_loader import load_snapshot

FIXTURES = Path(__file__).parent / "fixtures" / "github_api"
OWNER = "owner"
REPO = "sample-repo"
SHA = "abc123def456abc123def456abc123def456abc1"


@pytest.fixture
def mock_github():
    with respx.mock(
        base_url="https://api.github.com", assert_all_called=False
    ) as router:
        router.get(f"/repos/{OWNER}/{REPO}").mock(
            return_value=httpx.Response(
                200, json=json.loads((FIXTURES / "repo.json").read_text())
            )
        )
        router.get(f"/repos/{OWNER}/{REPO}/git/ref/heads/main").mock(
            return_value=httpx.Response(
                200, json=json.loads((FIXTURES / "ref.json").read_text())
            )
        )
        router.get(f"/repos/{OWNER}/{REPO}/git/trees/{SHA}").mock(
            return_value=httpx.Response(
                200, json=json.loads((FIXTURES / "tree.json").read_text())
            )
        )
        router.get(f"/repos/{OWNER}/{REPO}/contents/README.md").mock(
            return_value=httpx.Response(
                200, json=json.loads((FIXTURES / "readme_file.json").read_text())
            )
        )
        router.get(url__regex=f"/repos/{OWNER}/{REPO}/contents/.*").mock(
            return_value=httpx.Response(
                200,
                json={
                    "encoding": "base64",
                    "content": "cHJpbnQoJ2hlbGxvJyk=",
                },
            )
        )
        yield router


def test_snapshot_has_commit_sha(mock_github):
    snapshot = load_snapshot(OWNER, REPO)
    assert snapshot.commit_sha == SHA


def test_snapshot_captures_readme(mock_github):
    snapshot = load_snapshot(OWNER, REPO)
    assert snapshot.readme is not None
    assert "Sample Repo" in snapshot.readme.content


def test_snapshot_filters_noise(mock_github):
    snapshot = load_snapshot(OWNER, REPO)
    paths = [f.path for f in snapshot.files]
    # Excluded: node_modules, binary (.png), tree entry (src/), oversized file
    assert not any("node_modules" in p for p in paths)
    assert "image.png" not in paths
    assert "big_file.py" not in paths
    assert "src/" not in paths  # tree-type entry, not a blob


def test_snapshot_includes_source_files(mock_github):
    snapshot = load_snapshot(OWNER, REPO)
    paths = [f.path for f in snapshot.files]
    assert "README.md" in paths
    assert "main.py" in paths
    assert "utils.py" in paths
