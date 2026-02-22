"""Filter logic to decide which repo files to include in analysis."""

import os

# Directories to always skip (matched as path prefixes)
_EXCLUDED_DIRS = {
    "node_modules/",
    ".git/",
    "dist/",
    "build/",
    ".next/",
    "venv/",
    ".venv/",
    "__pycache__/",
    ".pytest_cache/",
    "coverage/",
    ".turbo/",
    "out/",
}

# Binary / non-text extensions to skip
_BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".bmp",
    ".pdf", ".zip", ".tar", ".gz", ".bz2", ".xz", ".rar", ".7z",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".wasm",
    ".ttf", ".woff", ".woff2", ".eot", ".otf",
    ".mp3", ".mp4", ".mov", ".avi", ".wav",
    ".pyc", ".pyo", ".pyd",
    ".lock",  # package lock files are noisy but we keep package.json
}

# Extensions we actively want
_INCLUDE_EXTENSIONS = {
    ".md", ".mdx", ".txt", ".rst",
    ".py", ".pyi",
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".json",  # kept selectively (size-filtered below)
    ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".graphql", ".gql",
    ".sql",
    ".sh", ".bash",
    ".env.example",
    ".dockerfile", "",  # files with no extension (Makefile, Dockerfile, etc.)
}

MAX_FILE_BYTES = 100_000  # 100 KB


def should_include(path: str, size_bytes: int, is_binary_guess: bool = False) -> bool:
    """Return True if the file at `path` should be included in analysis."""
    if is_binary_guess:
        return False

    # Exclude any path that starts with a blacklisted directory segment
    norm = path.lstrip("/")
    for excl in _EXCLUDED_DIRS:
        if norm.startswith(excl) or f"/{excl}" in f"/{norm}":
            return False

    if size_bytes > MAX_FILE_BYTES:
        return False

    ext = os.path.splitext(path)[1].lower()
    if ext in _BINARY_EXTENSIONS:
        return False

    # Only include files whose extension is in the allow-list
    # (empty string = no extension → Makefile, Dockerfile, etc.)
    return ext in _INCLUDE_EXTENSIONS
