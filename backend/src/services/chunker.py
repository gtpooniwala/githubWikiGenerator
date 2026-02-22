"""Split file contents into overlapping chunks with stable citation-ready IDs."""

import os
import re
from dataclasses import dataclass

WINDOW_SIZE = 60  # lines per sliding-window chunk
OVERLAP = 10  # lines of overlap between consecutive sliding windows
STEP = WINDOW_SIZE - OVERLAP

# Semantic boundary patterns
_PY_BOUNDARY = re.compile(r"^(async def |def |class )")
_JS_BOUNDARY = re.compile(
    r"^(export |function |class |const \w[\w$]* = (?:async )?[(\[])"
)


@dataclass(frozen=True)
class Chunk:
    chunk_id: str  # "{path}:{start_line}-{end_line}"
    path: str
    start_line: int  # 1-based, inclusive
    end_line: int  # 1-based, inclusive
    text: str


def _file_ext(path: str) -> str:
    return os.path.splitext(path)[1].lower()


def _semantic_boundaries(lines: list[str], path: str) -> list[int]:
    """Return sorted 0-based line indices that open a new semantic block."""
    ext = _file_ext(path)
    if ext == ".py":
        pattern = _PY_BOUNDARY
    elif ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
        pattern = _JS_BOUNDARY
    else:
        return []
    return [i for i, line in enumerate(lines) if pattern.match(line)]


def _make_chunks_from_lines(
    lines: list[str], path: str, offset: int = 0
) -> list[Chunk]:
    """Sliding-window chunker over a list of lines.

    Args:
        lines:  the line strings (with newlines).
        path:   file path used in chunk_id.
        offset: 0-based line index of lines[0] within the original file.
    """
    if not lines:
        return []
    chunks: list[Chunk] = []
    i = 0
    while i < len(lines):
        end_exclusive = min(i + WINDOW_SIZE, len(lines))
        start_1 = offset + i + 1  # 1-based
        end_1 = offset + end_exclusive  # 1-based inclusive
        text = "".join(lines[i:end_exclusive])
        chunks.append(
            Chunk(
                chunk_id=f"{path}:{start_1}-{end_1}",
                path=path,
                start_line=start_1,
                end_line=end_1,
                text=text,
            )
        )
        if end_exclusive == len(lines):
            break
        i += STEP
    return chunks


def chunk_file(path: str, content: str) -> list[Chunk]:
    """Split *content* of file at *path* into Chunk objects.

    Strategy:
    1. For Python / JS/TS files attempt semantic splitting on top-level
       boundaries (def / class / export / function …).
    2. For semantic chunks that are still > WINDOW_SIZE lines, sub-chunk
       with the sliding window so the max-lines invariant holds.
    3. For all other files (or when < 2 boundaries are found) fall back
       directly to the sliding window.

    Guarantees:
    - Every line of the file is covered by at least one chunk.
    - No chunk exceeds WINDOW_SIZE lines.
    - chunk_id strings are deterministic for the same input.
    """
    lines = content.splitlines(keepends=True)
    if not lines:
        return []

    boundaries = _semantic_boundaries(lines, path)

    # Need at least 1 boundary to do meaningful semantic splitting
    if not boundaries:
        return _make_chunks_from_lines(lines, path)

    chunks: list[Chunk] = []

    # --- Preamble (before the first boundary: imports, module docstrings) ---
    if boundaries[0] > 0:
        chunks.extend(_make_chunks_from_lines(lines[: boundaries[0]], path, offset=0))

    # --- Semantic segments ---
    sentinels = boundaries + [len(lines)]  # exclusive end for last segment
    for idx, start in enumerate(boundaries):
        end_exclusive = sentinels[idx + 1]
        segment = lines[start:end_exclusive]
        if len(segment) > WINDOW_SIZE:
            chunks.extend(_make_chunks_from_lines(segment, path, offset=start))
        else:
            start_1 = start + 1
            end_1 = end_exclusive
            chunks.append(
                Chunk(
                    chunk_id=f"{path}:{start_1}-{end_1}",
                    path=path,
                    start_line=start_1,
                    end_line=end_1,
                    text="".join(segment),
                )
            )

    return chunks
