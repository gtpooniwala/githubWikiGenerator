"""GitHub REST API client.

Rate-limit strategy
-------------------
* Without ``GITHUB_TOKEN``: 60 requests/hour (per IP).  Fine for light use
  but a repo with >50 files will exhaust this in a single run.
* With ``GITHUB_TOKEN``: 5 000 requests/hour primary limit plus secondary
  limits that GitHub does not fully disclose but roughly permit ~90 concurrent
  GET requests per minute.

All requests go through ``_get`` which:
  1. Inspects ``X-RateLimit-Remaining`` and sleeps until ``X-RateLimit-Reset``
     if we are at zero.
  2. Retries on ``429`` and rate-limit ``403`` responses, honouring the
     ``Retry-After`` header (or defaulting to 60 s).
  3. Retries on transient 5xx errors with exponential back-off.
  4. Raises immediately on all other 4xx errors.

Set the ``GITHUB_TOKEN`` environment variable to a personal access token
(classic or fine-grained, read-only) to use the higher quota.
"""

import base64
import os
import time
import warnings
from typing import Any

import httpx

GITHUB_API = "https://api.github.com"
_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# Maximum number of retry attempts for rate-limit / transient errors.
_MAX_RETRIES = 4

if not _TOKEN:
    warnings.warn(
        "GITHUB_TOKEN is not set.  Running unauthenticated with only 60 requests/hour. "
        "Set GITHUB_TOKEN to a read-only personal access token for the 5 000 req/hr quota.",
        stacklevel=1,
    )


def _headers() -> dict[str, str]:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if _TOKEN:
        h["Authorization"] = f"Bearer {_TOKEN}"
    return h


def _get(url: str, *, params: dict | None = None, timeout: float = 20) -> httpx.Response:
    """GET *url* with automatic rate-limit handling and retry.

    Raises:
        httpx.HTTPStatusError: On non-retriable 4xx errors.
        RuntimeError: If the rate limit is still exceeded after all retries.
    """
    for attempt in range(_MAX_RETRIES + 1):
        r = httpx.get(url, headers=_headers(), params=params, timeout=timeout)

        # ── Success ───────────────────────────────────────────────────────────
        if r.status_code < 300:
            # Proactive: if we're nearly out of quota, sleep until reset now
            # rather than hammering until we get a 429.
            remaining = int(r.headers.get("x-ratelimit-remaining", "1"))
            if remaining == 0:
                reset_at = int(r.headers.get("x-ratelimit-reset", "0"))
                wait = max(0.0, reset_at - time.time()) + 1.0
                time.sleep(wait)
            return r

        # ── Rate limited (primary or secondary) ──────────────────────────────
        is_rate_limited = r.status_code == 429 or (
            r.status_code == 403
            and "rate limit" in r.text.lower()
        )
        if is_rate_limited:
            if attempt == _MAX_RETRIES:
                r.raise_for_status()  # give up
            # Honour Retry-After if present, else fall back to x-ratelimit-reset
            retry_after_raw = r.headers.get("retry-after")
            if retry_after_raw is not None:
                wait = float(retry_after_raw)
            else:
                reset_at = int(r.headers.get("x-ratelimit-reset", "0"))
                wait = max(5.0, reset_at - time.time()) + 1.0
            time.sleep(wait)
            continue

        # ── Transient server error ────────────────────────────────────────────
        if r.status_code >= 500:
            if attempt == _MAX_RETRIES:
                r.raise_for_status()
            time.sleep(2 ** attempt)  # 1 s, 2 s, 4 s, 8 s
            continue

        # ── Non-retriable client error (404, 401, etc.) ───────────────────────
        r.raise_for_status()

    # Should be unreachable, but satisfy the type-checker.
    raise RuntimeError(f"Failed to GET {url} after {_MAX_RETRIES} retries")


def get_repo(owner: str, repo: str) -> dict[str, Any]:
    """Return repo metadata dict."""
    return _get(f"{GITHUB_API}/repos/{owner}/{repo}").json()


def get_branch_sha(owner: str, repo: str, branch: str) -> str:
    """Return the HEAD commit SHA for the given branch."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/git/ref/heads/{branch}"
    return _get(url).json()["object"]["sha"]


def get_tree(owner: str, repo: str, sha: str) -> list[dict[str, Any]]:
    """Return the full recursive tree for the given commit SHA."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{sha}"
    return _get(url, params={"recursive": "1"}, timeout=30).json().get("tree", [])


def get_file(owner: str, repo: str, path: str, ref_sha: str) -> str:
    """Return the decoded text content of a file at the given ref."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
    data = _get(url, params={"ref": ref_sha}).json()
    encoding = data.get("encoding", "")
    content = data.get("content", "")
    if encoding == "base64":
        return base64.b64decode(content).decode("utf-8", errors="replace")
    return content
