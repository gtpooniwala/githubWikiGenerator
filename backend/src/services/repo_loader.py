"""Builds a RepoSnapshot by fetching tree + file contents from GitHub."""

from services import github_client
from services.file_filter import should_include
from models.repo_snapshot import FileEntry, RepoSnapshot


def load_snapshot(owner: str, repo: str) -> RepoSnapshot:
    """Fetch repo metadata, tree, and selected file contents."""
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

    # 5. Download content for each candidate
    files: list[FileEntry] = []
    for item in candidates:
        try:
            content = github_client.get_file(owner, repo, item["path"], commit_sha)
            files.append(
                FileEntry(path=item["path"], size=item.get("size", 0), content=content)
            )
        except Exception:
            # Skip files that fail to download (permissions, encoding issues, etc.)
            pass

    return RepoSnapshot(
        owner=owner,
        repo=repo,
        default_branch=default_branch,
        commit_sha=commit_sha,
        files=files,
    )
