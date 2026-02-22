"""GitHub REST API client (unauthenticated; set GITHUB_TOKEN env var for higher rate limits)."""

import os
from typing import Any

import httpx

GITHUB_API = "https://api.github.com"
_TOKEN = os.environ.get("GITHUB_TOKEN", "")


def _headers() -> dict[str, str]:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if _TOKEN:
        h["Authorization"] = f"Bearer {_TOKEN}"
    return h


def get_repo(owner: str, repo: str) -> dict[str, Any]:
    """Return repo metadata dict."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}"
    r = httpx.get(url, headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()


def get_branch_sha(owner: str, repo: str, branch: str) -> str:
    """Return the HEAD commit SHA for the given branch."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/git/ref/heads/{branch}"
    r = httpx.get(url, headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()["object"]["sha"]


def get_tree(owner: str, repo: str, sha: str) -> list[dict[str, Any]]:
    """Return the full recursive tree for the given commit SHA."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{sha}"
    r = httpx.get(url, params={"recursive": "1"}, headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json().get("tree", [])


def get_file(owner: str, repo: str, path: str, ref_sha: str) -> str:
    """Return the decoded text content of a file at the given ref."""
    import base64

    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
    r = httpx.get(url, params={"ref": ref_sha}, headers=_headers(), timeout=15)
    r.raise_for_status()
    data = r.json()
    encoding = data.get("encoding", "")
    content = data.get("content", "")
    if encoding == "base64":
        return base64.b64decode(content).decode("utf-8", errors="replace")
    return content
