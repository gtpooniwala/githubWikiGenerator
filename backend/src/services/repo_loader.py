"""Builds a RepoSnapshot by fetching tree + file contents from GitHub."""

from concurrent.futures import ThreadPoolExecutor, as_completed

from services import github_client
from services.file_filter import should_include
from models.repo_snapshot import FileEntry, RepoSnapshot

# Fetch up to this many files in parallel.  High enough to be fast; low
# enough not to overwhelm the GitHub API or trigger secondary-rate-limits.
_FETCH_WORKERS = 10


def _fetch_one(
    owner: str, repo: str, path: str, size: int, commit_sha: str
) -> FileEntry | None:
    """Download a single file; return None on any error."""
    try:
        content = github_client.get_file(owner, repo, path, commit_sha)
        return FileEntry(path=path, size=size, content=content)
    except Exception:
        return None


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
