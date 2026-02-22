"""Extract non-LLM signals from a repo snapshot to guide feature discovery."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from models.repo_snapshot import FileEntry


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReadingHeading:
    level: int    # 1 = H1, 2 = H2, etc.
    text: str


@dataclass(frozen=True)
class RouteSignal:
    method: str   # GET, POST, PUT, DELETE, PATCH, ANY
    path: str     # URL pattern, e.g. "/api/generate"
    file_path: str
    line_no: int  # 1-based


@dataclass(frozen=True)
class EntryPoint:
    kind: str     # "npm-script", "python-main", "cli-module"
    name: str     # script name or module path
    command: str  # command / module path


@dataclass
class RepoSignals:
    readme_headings: list[ReadingHeading] = field(default_factory=list)
    routes: list[RouteSignal] = field(default_factory=list)
    entrypoints: list[EntryPoint] = field(default_factory=list)


# ---------------------------------------------------------------------------
# README headings
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)", re.MULTILINE)


def extract_readme_signals(readme_md: str) -> list[ReadingHeading]:
    """Return an ordered list of headings from a markdown string."""
    return [
        ReadingHeading(level=len(m.group(1)), text=m.group(2).strip())
        for m in _HEADING_RE.finditer(readme_md)
    ]


# ---------------------------------------------------------------------------
# Route signals
# ---------------------------------------------------------------------------

# FastAPI / Starlette: @app.get("/path") or @router.post("/path")
_FASTAPI_ROUTE = re.compile(
    r'@\w+\.(get|post|put|delete|patch|options|head|trace)\s*\(\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)

# Express: app.get('/path', ...) or router.post('/path', ...)
_EXPRESS_ROUTE = re.compile(
    r'\b\w+\.(get|post|put|delete|patch|options|all)\s*\(\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)

# Next.js App Router: export async function GET(...) or export function POST(...)
_NEXTJS_ROUTE = re.compile(
    r"^export\s+(?:async\s+)?function\s+(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\s*\(",
    re.MULTILINE,
)


def _is_python(path: str) -> bool:
    return path.endswith(".py")


def _is_js_ts(path: str) -> bool:
    return path.endswith((".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"))


def _is_nextjs_route(path: str) -> bool:
    return _is_js_ts(path) and path.endswith("route.ts") or path.endswith("route.js")


def extract_route_signals(files: list[FileEntry]) -> list[RouteSignal]:
    """Scan file contents for route/endpoint definitions."""
    signals: list[RouteSignal] = []

    for f in files:
        lines = f.content.splitlines()

        if _is_python(f.path):
            for i, line in enumerate(lines):
                for m in _FASTAPI_ROUTE.finditer(line):
                    signals.append(RouteSignal(
                        method=m.group(1).upper(),
                        path=m.group(2),
                        file_path=f.path,
                        line_no=i + 1,
                    ))

        elif _is_js_ts(f.path):
            # Express-style routes (all JS/TS)
            for i, line in enumerate(lines):
                for m in _EXPRESS_ROUTE.finditer(line):
                    signals.append(RouteSignal(
                        method=m.group(1).upper(),
                        path=m.group(2),
                        file_path=f.path,
                        line_no=i + 1,
                    ))

            # Next.js App Router export handlers
            if "route.ts" in f.path or "route.js" in f.path:
                for m in _NEXTJS_ROUTE.finditer(f.content):
                    line_no = f.content[: m.start()].count("\n") + 1
                    signals.append(RouteSignal(
                        method=m.group(1).upper(),
                        path=f.path,  # the file path IS the route in Next.js
                        file_path=f.path,
                        line_no=line_no,
                    ))

    return signals


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

_PYTHON_MAIN_RE = re.compile(r'if\s+__name__\s*==\s*["\']__main__["\']')


def extract_entrypoints(files: list[FileEntry]) -> list[EntryPoint]:
    """Identify npm scripts, Python __main__ blocks, and CLI modules."""
    entrypoints: list[EntryPoint] = []

    for f in files:
        # npm scripts from package.json
        if f.path.endswith("package.json") and "node_modules" not in f.path:
            try:
                pkg = json.loads(f.content)
                scripts = pkg.get("scripts", {})
                for name, cmd in scripts.items():
                    entrypoints.append(EntryPoint(kind="npm-script", name=name, command=cmd))
            except (json.JSONDecodeError, AttributeError):
                pass

        # Python __main__ guard
        elif _is_python(f.path) and _PYTHON_MAIN_RE.search(f.content):
            entrypoints.append(EntryPoint(
                kind="python-main",
                name=f.path,
                command=f"python {f.path}",
            ))

        # Dedicated CLI modules
        elif _is_python(f.path) and any(
            f.path.endswith(n) for n in ("__main__.py", "cli.py", "manage.py")
        ):
            entrypoints.append(EntryPoint(
                kind="cli-module",
                name=f.path,
                command=f"python {f.path}",
            ))

    return entrypoints
