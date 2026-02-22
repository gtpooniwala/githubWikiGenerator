import pytest

from services.chunker import Chunk, WINDOW_SIZE, chunk_file


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _all_lines_covered(content: str, chunks: list[Chunk]) -> bool:
    """Every 1-based line index must appear in at least one chunk."""
    lines = content.splitlines(keepends=True)
    if not lines:
        return True
    covered = set()
    for c in chunks:
        for ln in range(c.start_line, c.end_line + 1):
            covered.add(ln)
    return covered == set(range(1, len(lines) + 1))


def _max_chunk_lines(chunks: list[Chunk]) -> int:
    return max((c.end_line - c.start_line + 1) for c in chunks) if chunks else 0


# ---------------------------------------------------------------------------
# Empty / trivial inputs
# ---------------------------------------------------------------------------


def test_empty_content_returns_no_chunks():
    assert chunk_file("empty.py", "") == []


def test_single_line_file():
    chunks = chunk_file("single.py", "x = 1\n")
    assert len(chunks) == 1
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 1


# ---------------------------------------------------------------------------
# Sliding-window fallback (Markdown / plain text)
# ---------------------------------------------------------------------------


def _make_content(n_lines: int) -> str:
    return "".join(f"line {i}\n" for i in range(1, n_lines + 1))


def test_sliding_window_full_coverage_small():
    content = _make_content(30)
    chunks = chunk_file("notes.md", content)
    assert _all_lines_covered(content, chunks)


def test_sliding_window_full_coverage_exact_window():
    content = _make_content(WINDOW_SIZE)
    chunks = chunk_file("notes.md", content)
    assert _all_lines_covered(content, chunks)


def test_sliding_window_full_coverage_large():
    content = _make_content(200)
    chunks = chunk_file("notes.md", content)
    assert _all_lines_covered(content, chunks)
    assert _max_chunk_lines(chunks) <= WINDOW_SIZE


def test_sliding_window_overlap():
    """With 60-line window and 10-line overlap, a 70-line file needs 2 chunks
    and lines 61-60 appear in both."""
    content = _make_content(70)
    chunks = chunk_file("notes.md", content)
    assert len(chunks) == 2
    # Overlap region: lines 51-60 should appear in both chunks
    line_count: dict[int, int] = {}
    for c in chunks:
        for ln in range(c.start_line, c.end_line + 1):
            line_count[ln] = line_count.get(ln, 0) + 1
    overlap_lines = range(51, 61)
    assert all(line_count[ln] == 2 for ln in overlap_lines)


# ---------------------------------------------------------------------------
# Python semantic splitting
# ---------------------------------------------------------------------------

PY_CONTENT = """\
import os

CONSTANT = 42


def foo():
    return 1


def bar(x):
    return x + 1


class MyClass:
    def method(self):
        pass
"""


def test_python_semantic_full_coverage():
    chunks = chunk_file("module.py", PY_CONTENT)
    assert _all_lines_covered(PY_CONTENT, chunks)


def test_python_semantic_boundaries_detected():
    chunks = chunk_file("module.py", PY_CONTENT)
    # Should have a chunk starting at 'def foo', 'def bar', 'class MyClass'
    start_lines = {c.start_line for c in chunks}
    lines = PY_CONTENT.splitlines()
    foo_line = next(i + 1 for i, l in enumerate(lines) if l.startswith("def foo"))
    bar_line = next(i + 1 for i, l in enumerate(lines) if l.startswith("def bar"))
    cls_line = next(i + 1 for i, l in enumerate(lines) if l.startswith("class My"))
    assert foo_line in start_lines
    assert bar_line in start_lines
    assert cls_line in start_lines


def test_python_max_chunk_size():
    # Generate a large Python file with many functions
    lines = ["import os\n"]
    for i in range(30):
        lines += [f"def func_{i}():\n"] + [f"    x = {j}\n" for j in range(5)] + ["\n"]
    content = "".join(lines)
    chunks = chunk_file("big.py", content)
    assert _all_lines_covered(content, chunks)
    assert _max_chunk_lines(chunks) <= WINDOW_SIZE


# ---------------------------------------------------------------------------
# JS/TS semantic splitting
# ---------------------------------------------------------------------------

TS_CONTENT = """\
import React from 'react';

const API_URL = 'http://localhost';

export function fetchData(url: string) {
  return fetch(url);
}

export const handler = async (req: Request) => {
  return Response.json({ ok: true });
};

class Service {
  constructor() {}
}
"""


def test_ts_semantic_full_coverage():
    chunks = chunk_file("api.ts", TS_CONTENT)
    assert _all_lines_covered(TS_CONTENT, chunks)


def test_ts_semantic_max_chunk_size():
    lines = ["import React from 'react';\n"]
    for i in range(20):
        lines += (
            [f"export function fn{i}() {{\n"]
            + [f"  const x{j} = {j};\n" for j in range(5)]
            + ["}\n\n"]
        )
    content = "".join(lines)
    chunks = chunk_file("big.ts", content)
    assert _all_lines_covered(content, chunks)
    assert _max_chunk_lines(chunks) <= WINDOW_SIZE


# ---------------------------------------------------------------------------
# Stable / deterministic IDs
# ---------------------------------------------------------------------------


def test_chunk_ids_are_deterministic():
    chunks1 = chunk_file("module.py", PY_CONTENT)
    chunks2 = chunk_file("module.py", PY_CONTENT)
    assert [c.chunk_id for c in chunks1] == [c.chunk_id for c in chunks2]


def test_chunk_id_format():
    chunks = chunk_file("src/main.py", PY_CONTENT)
    for c in chunks:
        assert c.chunk_id == f"src/main.py:{c.start_line}-{c.end_line}"


def test_chunk_ids_are_unique():
    chunks = chunk_file("module.py", PY_CONTENT)
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))
