"""Tests for services/import_graph.py."""

import pytest

from models.repo_snapshot import FileEntry
from services.import_graph import build_import_graph


def _file(path: str, content: str = "") -> FileEntry:
    return FileEntry(path=path, size=len(content), content=content)


# ---------------------------------------------------------------------------
# Python – absolute imports
# ---------------------------------------------------------------------------

class TestPythonAbsoluteImports:
    def test_simple_import(self):
        files = [
            _file("main.py", "import utils"),
            _file("utils.py", ""),
        ]
        g = build_import_graph(files)
        assert "utils.py" in g["main.py"]

    def test_dotted_import(self):
        files = [
            _file("app/main.py", "import app.models"),
            _file("app/models.py", ""),
        ]
        g = build_import_graph(files)
        assert "app/models.py" in g["app/main.py"]

    def test_from_import(self):
        files = [
            _file("app/router.py", "from app.auth import require_key"),
            _file("app/auth.py", ""),
        ]
        g = build_import_graph(files)
        assert "app/auth.py" in g["app/router.py"]

    def test_package_init_resolved(self):
        files = [
            _file("main.py", "import models"),
            _file("models/__init__.py", ""),
        ]
        g = build_import_graph(files)
        assert "models/__init__.py" in g["main.py"]

    def test_external_package_ignored(self):
        files = [
            _file("main.py", "import fastapi\nimport os\nimport re"),
        ]
        g = build_import_graph(files)
        assert g["main.py"] == []

    def test_multiline_imports(self):
        content = "import os\nimport utils\nfrom services import auth\n"
        files = [
            _file("run.py", content),
            _file("utils.py", ""),
            _file("services/auth.py", ""),
        ]
        g = build_import_graph(files)
        assert "utils.py" in g["run.py"]
        assert "services/auth.py" in g["run.py"]


# ---------------------------------------------------------------------------
# Python – relative imports
# ---------------------------------------------------------------------------

class TestPythonRelativeImports:
    def test_dot_import_same_package(self):
        files = [
            _file("services/chunker.py", "from . import signals"),
            _file("services/signals.py", ""),
        ]
        g = build_import_graph(files)
        assert "services/signals.py" in g["services/chunker.py"]

    def test_dot_module_import(self):
        files = [
            _file("services/chunker.py", "from .signals import extract"),
            _file("services/signals.py", ""),
        ]
        g = build_import_graph(files)
        assert "services/signals.py" in g["services/chunker.py"]

    def test_double_dot_parent_import(self):
        files = [
            _file("services/sub/helper.py", "from .. import signals"),
            _file("services/signals.py", ""),
        ]
        g = build_import_graph(files)
        assert "services/signals.py" in g["services/sub/helper.py"]

    def test_relative_external_not_added(self):
        """Relative import that doesn't resolve to any file → ignored."""
        files = [
            _file("pkg/a.py", "from . import nonexistent"),
        ]
        g = build_import_graph(files)
        assert g["pkg/a.py"] == []


# ---------------------------------------------------------------------------
# JS / TS imports
# ---------------------------------------------------------------------------

class TestJavaScriptImports:
    def test_relative_named_import(self):
        files = [
            _file("src/app.ts", "import { foo } from './utils'"),
            _file("src/utils.ts", ""),
        ]
        g = build_import_graph(files)
        assert "src/utils.ts" in g["src/app.ts"]

    def test_relative_import_without_extension(self):
        files = [
            _file("src/index.ts", "import api from './api'"),
            _file("src/api.ts", ""),
        ]
        g = build_import_graph(files)
        assert "src/api.ts" in g["src/index.ts"]

    def test_index_file_resolution(self):
        files = [
            _file("src/app.ts", "import { Router } from './router'"),
            _file("src/router/index.ts", ""),
        ]
        g = build_import_graph(files)
        assert "src/router/index.ts" in g["src/app.ts"]

    def test_require_syntax(self):
        files = [
            _file("server.js", "const db = require('./db')"),
            _file("db.js", ""),
        ]
        g = build_import_graph(files)
        assert "db.js" in g["server.js"]

    def test_external_npm_package_ignored(self):
        files = [
            _file("src/page.tsx", "import React from 'react'\nimport { useState } from 'react'"),
        ]
        g = build_import_graph(files)
        assert g["src/page.tsx"] == []

    def test_parent_directory_import(self):
        files = [
            _file("src/components/Button.tsx", "import { theme } from '../lib/theme'"),
            _file("src/lib/theme.ts", ""),
        ]
        g = build_import_graph(files)
        assert "src/lib/theme.ts" in g["src/components/Button.tsx"]


# ---------------------------------------------------------------------------
# Graph structure guarantees
# ---------------------------------------------------------------------------

class TestGraphStructure:
    def test_every_file_appears_as_key(self):
        files = [
            _file("a.py", ""),
            _file("b.py", ""),
            _file("c.py", "import a"),
        ]
        g = build_import_graph(files)
        assert set(g.keys()) == {"a.py", "b.py", "c.py"}

    def test_edges_are_sorted_and_deduplicated(self):
        files = [
            _file("main.py", "import utils\nimport utils\nimport models"),
            _file("utils.py", ""),
            _file("models.py", ""),
        ]
        g = build_import_graph(files)
        edges = g["main.py"]
        assert edges == sorted(edges)
        assert len(edges) == len(set(edges))

    def test_no_self_loops(self):
        files = [
            _file("utils.py", "from utils import something"),
        ]
        g = build_import_graph(files)
        assert "utils.py" not in g["utils.py"]

    def test_non_code_files_ignored(self):
        """Non-.py/.ts/.js files should still appear as keys but have no edges."""
        files = [
            _file("README.md", "import foo"),
            _file("data.json", '{"x": 1}'),
        ]
        g = build_import_graph(files)
        assert g["README.md"] == []
        assert g["data.json"] == []

    def test_empty_snapshot(self):
        assert build_import_graph([]) == {}

    def test_mixed_python_and_ts_repo(self):
        files = [
            _file("backend/main.py", "import backend.auth"),
            _file("backend/auth.py", ""),
            _file("frontend/src/app.ts", "import { api } from './api'"),
            _file("frontend/src/api.ts", ""),
        ]
        g = build_import_graph(files)
        assert "backend/auth.py" in g["backend/main.py"]
        assert "frontend/src/api.ts" in g["frontend/src/app.ts"]
