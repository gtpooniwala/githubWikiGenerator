"""Build a file-to-file import graph for a repo snapshot.

Supports:
  - Python: ``import x``, ``from x import y`` (incl. relative ``from . import y``)
  - JS/TS:  ``import ... from '...'``, ``require('...')``

Only intra-repo edges are emitted; external packages are ignored.
"""

from __future__ import annotations

import posixpath
import re
from collections import defaultdict

from models.repo_snapshot import FileEntry

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Python: "import a.b.c" or "import a.b.c as alias"
_PY_IMPORT = re.compile(r"^\s*import\s+([\w.]+)", re.MULTILINE)

# Python: "from a.b import c" or "from . import c" or "from ..pkg import c"
# Group 1 = module/dot-prefix, Group 2 = first imported name (sufficient for path resolution)
_PY_FROM = re.compile(r"^\s*from\s+(\.{0,3}[\w.]*?)\s+import\s+(\w+)", re.MULTILINE)

# JS/TS: import ... from './foo' or import './foo'
_JS_IMPORT = re.compile(r"""import\s+(?:[^'"]*\s+from\s+)?['"]([^'"]+)['"]""")

# JS/TS: require('./foo')
_JS_REQUIRE = re.compile(r"""require\s*\(\s*['"]([^'"]+)['"]\s*\)""")

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

_PY_EXTENSIONS = (".py",)
_JS_EXTENSIONS = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")


def _dir(path: str) -> str:
    """Return the directory portion of a repo-relative path (always '/' separated)."""
    return posixpath.dirname(path)


def _normalise(path: str) -> str:
    return posixpath.normpath(path)


def _resolve_relative_js(
    source_file: str, specifier: str, repo_paths: set[str]
) -> str | None:
    """Resolve a relative JS/TS import specifier to a repo path, or None."""
    if not specifier.startswith("."):
        return None  # external package

    base = _dir(source_file)
    candidate = _normalise(posixpath.join(base, specifier))

    # exact match
    if candidate in repo_paths:
        return candidate

    # try appending each known extension
    for ext in _JS_EXTENSIONS:
        with_ext = candidate + ext
        if with_ext in repo_paths:
            return with_ext

    # index file inside a directory
    for ext in _JS_EXTENSIONS:
        index = _normalise(posixpath.join(candidate, "index" + ext))
        if index in repo_paths:
            return index

    return None


def _module_to_path(module: str) -> str:
    """Convert a dotted Python module name to a repo-relative path fragment."""
    return module.replace(".", "/")


def _resolve_python_import(
    source_file: str, module: str, repo_paths: set[str]
) -> str | None:
    """Resolve a Python module string to a repo path, or None for external packages."""
    candidate_base = _module_to_path(module)

    # Try direct: module/path.py or module/path/__init__.py
    for suffix in (".py", "/__init__.py"):
        p = _normalise(candidate_base + suffix)
        if p in repo_paths:
            return p

    # Try anchored under src/ (common layout)
    for prefix in ("src/", "backend/src/"):
        for suffix in (".py", "/__init__.py"):
            p = _normalise(prefix + candidate_base + suffix)
            if p in repo_paths:
                return p

    return None


def _resolve_python_relative(
    source_file: str, specifier: str, repo_paths: set[str]
) -> str | None:
    """Resolve a relative Python from-import (e.g. '.utils', '..models') to a repo path."""
    # Count leading dots
    dots = len(specifier) - len(specifier.lstrip("."))
    module_part = specifier.lstrip(".")

    # Start from the source file's directory; go up (dots-1) levels
    base = _dir(source_file)
    for _ in range(dots - 1):
        base = _dir(base)

    if module_part:
        candidate_base = _normalise(posixpath.join(base, _module_to_path(module_part)))
    else:
        candidate_base = base

    for suffix in (".py", "/__init__.py"):
        p = _normalise(candidate_base + suffix)
        if p in repo_paths:
            return p

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

ImportGraph = dict[str, list[str]]
"""Mapping from each file path to the list of repo files it imports."""


def build_import_graph(files: list[FileEntry]) -> ImportGraph:
    """Return a file→[imported_files] adjacency list for all files in *files*.

    Only intra-repo edges are included; external libraries are silently skipped.
    Each list is deduplicated and sorted for determinism.
    """
    repo_paths: set[str] = {f.path for f in files}
    graph: dict[str, set[str]] = defaultdict(set)

    for entry in files:
        path = entry.path
        content = entry.content

        ext = posixpath.splitext(path)[1].lower()

        if ext in _PY_EXTENSIONS:
            # Absolute imports
            for m in _PY_IMPORT.finditer(content):
                resolved = _resolve_python_import(path, m.group(1), repo_paths)
                if resolved and resolved != path:
                    graph[path].add(resolved)

            # from-imports (absolute and relative)
            for m in _PY_FROM.finditer(content):
                specifier = m.group(1)
                imported_name = m.group(2)
                if specifier.startswith("."):
                    # bare dot(s): "from . import signals" → treat as ".signals"
                    if not specifier.lstrip("."):
                        specifier = specifier + imported_name
                    resolved = _resolve_python_relative(path, specifier, repo_paths)
                else:
                    # absolute: try the module itself first, then module.name as submodule
                    resolved = _resolve_python_import(path, specifier, repo_paths)
                    if resolved is None and specifier:
                        resolved = _resolve_python_import(
                            path, specifier + "." + imported_name, repo_paths
                        )
                if resolved and resolved != path:
                    graph[path].add(resolved)

        elif ext in _JS_EXTENSIONS:
            for m in _JS_IMPORT.finditer(content):
                resolved = _resolve_relative_js(path, m.group(1), repo_paths)
                if resolved and resolved != path:
                    graph[path].add(resolved)
            for m in _JS_REQUIRE.finditer(content):
                resolved = _resolve_relative_js(path, m.group(1), repo_paths)
                if resolved and resolved != path:
                    graph[path].add(resolved)

        # Ensure every file appears as a key even with no outgoing edges
        if path not in graph:
            graph[path] = set()

    return {k: sorted(v) for k, v in graph.items()}
