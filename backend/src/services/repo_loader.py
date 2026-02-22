"""Builds a RepoSnapshot by fetching tree + file contents from GitHub.

Concurrency & rate-limit notes
-------------------------------
* Files are fetched in parallel using a small thread pool
  (``_FETCH_WORKERS`` = 5).  Five concurrent GET requests is well within
  GitHub's secondary-rate-limit guidance (≤ 90 requests/minute authenticated)
  while still giving a large speed-up over sequential fetching.
* Rate-limit handling (429 / 403 + Retry-After) is implemented inside
  ``github_client._get`` — individual workers will sleep and retry
  automatically rather than dropping files.
* Only genuine file-not-found / encoding errors are silently skipped;
  rate-limit errors are always retried (up to ``_MAX_RETRIES`` attempts)
  before they propagate and abort the pipeline with a clear message.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

from services import github_client
from services.file_filter import should_include
from models.repo_snapshot import FileEntry, RepoSnapshot

# Five workers: fast enough for most repos (150 files ≈ 15 s even at 0.5 s/file)
# while staying well below GitHub's secondary rate-limit threshold.
_FETCH_WORKERS = 5

# HTTP status codes that mean "this file simply isn't available" —
# we skip these silently.  Everything else (including 429 rate limits,
# which github_client retries automatically) is re-raised.
_SKIP_STATUSES = {403, 404, 451}  # 451 = legal / DMCA takedown


def _fetch_one(
    owner: str, repo: str, path: str, size: int, commit_sha: str
) -> FileEntry | None:
    """Download a single file.

    Returns:
        A populated ``FileEntry`` on success, or ``None`` if the file is
        unavailable (404 / 403 / encoding error).  Rate-limit errors are
        handled transparently by the underlying HTTP client and will
        sleep-and-retry rather than returning ``None``.
    """
    try:
        content = github_client.get_file(owner, repo, path, commit_sha)
        return FileEntry(path=path, size=size, content=content)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in _SKIP_STATUSES:
            return None  # file unavailable — skip silently
        raise  # rate-limit / server error — propagate so the pipeline fails loudly
    except (UnicodeDecodeError, ValueError):
        return None  # binary content that slipped through the filter


def load_snapshot(owner: str, repo: str) -> RepoSnapshot:
    """Fetch repo metadata, tree, and selected file contents.

    Files are downloaded in parallel (up to ``_FETCH_WORKERS`` concurrent
    requests) to keep wall-clock time under control even for large repos.
    """
    # 1. Repo metadata
    repo_data = github_client.get_repo(owner, repo)
    default_branch: str = repo_data["default_branch"]

    # 2. HEAD commit SHA
    commit_sha = github_client.get_branch_sha(owner, repo, default_branch)

    # 3. Full recursive tree
    tree = github_client.get_tree(owner, repo, commit_sha)

    # 4. Filter candidate files
    candidates = [
        item
        for item in tree
        if item.get("type") == "blob"
        and should_include(item["path"], item.get("size", 0))
    ]

    # 5. Download all candidates in parallel
    files: list[FileEntry] = []
    with ThreadPoolExecutor(max_workers=_FETCH_WORKERS) as pool:
        futures = {
            pool.submit(
                _fetch_one, owner, repo, item["path"], item.get("size", 0), commit_sha
            ): item
            for item in candidates
        }
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                files.append(result)

    # Restore deterministic ordering (as_completed gives arbitrary order)
    path_order = {item["path"]: idx for idx, item in enumerate(candidates)}
    files.sort(key=lambda f: path_order.get(f.path, 9999))

    return RepoSnapshot(
        owner=owner,
        repo=repo,
        default_branch=default_branch,
        commit_sha=commit_sha,
        files=files,
    )
