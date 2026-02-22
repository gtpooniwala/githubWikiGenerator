from dataclasses import dataclass, field


@dataclass
class FileEntry:
    path: str
    size: int
    content: str


@dataclass
class RepoSnapshot:
    owner: str
    repo: str
    default_branch: str
    commit_sha: str
    files: list[FileEntry] = field(default_factory=list)

    @property
    def readme(self) -> FileEntry | None:
        """Return the README file if present."""
        for f in self.files:
            if f.path.lower() in ("readme.md", "readme.rst", "readme.txt", "readme"):
                return f
        return None
