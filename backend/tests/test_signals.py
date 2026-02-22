import pytest

from models.repo_snapshot import FileEntry
from services.signals import (
    EntryPoint,
    ReadingHeading,
    RouteSignal,
    extract_entrypoints,
    extract_readme_signals,
    extract_route_signals,
)


# ---------------------------------------------------------------------------
# README headings
# ---------------------------------------------------------------------------

README = """\
# My Project

Some intro text.

## Features

### Authentication

## Installation

#### Step 1
"""


def test_readme_headings_levels():
    headings = extract_readme_signals(README)
    levels = [h.level for h in headings]
    assert levels == [1, 2, 3, 2, 4]


def test_readme_headings_text():
    headings = extract_readme_signals(README)
    texts = [h.text for h in headings]
    assert texts == [
        "My Project",
        "Features",
        "Authentication",
        "Installation",
        "Step 1",
    ]


def test_readme_empty():
    assert extract_readme_signals("") == []


def test_readme_no_headings():
    assert extract_readme_signals("Just some paragraph text.\n") == []


def test_readme_signals_deterministic():
    assert extract_readme_signals(README) == extract_readme_signals(README)


# ---------------------------------------------------------------------------
# Route signals – FastAPI
# ---------------------------------------------------------------------------

FASTAPI_CONTENT = """\
from fastapi import APIRouter
router = APIRouter()

@router.get("/health")
def health(): ...

@router.post("/api/generate")
def generate(): ...

@app.delete("/items/{id}")
def delete_item(): ...
"""


def test_fastapi_routes_detected():
    files = [
        FileEntry(
            path="src/main.py", size=len(FASTAPI_CONTENT), content=FASTAPI_CONTENT
        )
    ]
    routes = extract_route_signals(files)
    methods = {r.method for r in routes}
    paths = {r.path for r in routes}
    assert "GET" in methods
    assert "POST" in methods
    assert "DELETE" in methods
    assert "/health" in paths
    assert "/api/generate" in paths


def test_fastapi_route_line_numbers():
    files = [
        FileEntry(
            path="src/main.py", size=len(FASTAPI_CONTENT), content=FASTAPI_CONTENT
        )
    ]
    routes = extract_route_signals(files)
    health = next(r for r in routes if r.path == "/health")
    assert health.line_no >= 1


def test_fastapi_routes_carry_file_path():
    files = [
        FileEntry(path="backend/routers/api.py", size=100, content=FASTAPI_CONTENT)
    ]
    routes = extract_route_signals(files)
    assert all(r.file_path == "backend/routers/api.py" for r in routes)


# ---------------------------------------------------------------------------
# Route signals – Next.js App Router
# ---------------------------------------------------------------------------

NEXTJS_ROUTE_CONTENT = """\
import { NextRequest } from 'next/server';

export async function GET(req: NextRequest) {
  return Response.json({ ok: true });
}

export async function POST(req: NextRequest) {
  const body = await req.json();
  return Response.json(body);
}
"""


def test_nextjs_routes_detected():
    files = [
        FileEntry(
            path="src/app/api/generate/route.ts",
            size=len(NEXTJS_ROUTE_CONTENT),
            content=NEXTJS_ROUTE_CONTENT,
        )
    ]
    routes = extract_route_signals(files)
    methods = {r.method for r in routes}
    assert "GET" in methods
    assert "POST" in methods


# ---------------------------------------------------------------------------
# Route signals – Express
# ---------------------------------------------------------------------------

EXPRESS_CONTENT = """\
const express = require('express');
const router = express.Router();

router.get('/users', (req, res) => res.json([]));
router.post('/users', (req, res) => res.json({}));
router.delete('/users/:id', (req, res) => res.json({}));
"""


def test_express_routes_detected():
    files = [
        FileEntry(
            path="routes/users.js", size=len(EXPRESS_CONTENT), content=EXPRESS_CONTENT
        )
    ]
    routes = extract_route_signals(files)
    methods = {r.method for r in routes}
    assert "GET" in methods
    assert "POST" in methods
    assert "DELETE" in methods


def test_route_signals_deterministic():
    files = [FileEntry(path="src/main.py", size=100, content=FASTAPI_CONTENT)]
    assert extract_route_signals(files) == extract_route_signals(files)


def test_non_code_file_has_no_routes():
    files = [FileEntry(path="README.md", size=100, content=README)]
    assert extract_route_signals(files) == []


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

PKG_JSON = """\
{
  "name": "frontend",
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start"
  }
}
"""

PYTHON_MAIN = """\
def run():
    print("hello")

if __name__ == "__main__":
    run()
"""


def test_npm_scripts_extracted():
    files = [
        FileEntry(path="frontend/package.json", size=len(PKG_JSON), content=PKG_JSON)
    ]
    eps = extract_entrypoints(files)
    names = {e.name for e in eps}
    assert "dev" in names
    assert "build" in names
    assert "start" in names
    assert all(e.kind == "npm-script" for e in eps)


def test_python_main_guard_detected():
    files = [FileEntry(path="src/main.py", size=len(PYTHON_MAIN), content=PYTHON_MAIN)]
    eps = extract_entrypoints(files)
    assert any(e.kind == "python-main" for e in eps)


def test_cli_module_detected():
    content = "import click\n@click.command()\ndef cli(): pass\n"
    files = [FileEntry(path="src/cli.py", size=len(content), content=content)]
    eps = extract_entrypoints(files)
    assert any(e.kind == "cli-module" for e in eps)


def test_node_modules_package_json_ignored():
    files = [
        FileEntry(
            path="node_modules/react/package.json",
            size=10,
            content='{"scripts": {"test": "jest"}}',
        )
    ]
    eps = extract_entrypoints(files)
    assert eps == []


def test_entrypoints_deterministic():
    files = [FileEntry(path="package.json", size=len(PKG_JSON), content=PKG_JSON)]
    assert extract_entrypoints(files) == extract_entrypoints(files)
