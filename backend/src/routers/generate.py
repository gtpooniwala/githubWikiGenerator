import asyncio
import json
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from auth import require_api_key
from models.schemas import GenerateRequest, GenerateResponse
from services.chunker import chunk_file
from services.pipeline import run_pipeline
from services.repo_loader import load_snapshot
from services.signals import (
    RepoSignals,
    extract_entrypoints,
    extract_readme_signals,
    extract_route_signals,
)

router = APIRouter(prefix="/api")


def _sse_message(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _parse_repo_id(repo_url: str) -> str:
    """Extract 'owner/repo' from a GitHub URL."""
    url = str(repo_url).removesuffix("/").removesuffix(".git").removesuffix("/")
    parts = url.split("github.com/")
    if len(parts) != 2:
        raise ValueError(f"Cannot parse repo_id from URL: {repo_url}")
    return parts[1]


async def _run_pipeline(repo_url: str) -> AsyncIterator[str]:
    """Run the implemented pipeline stages, yielding SSE messages as each completes."""
    repo_id = _parse_repo_id(repo_url)
    owner, repo = repo_id.split("/", 1)

    # Emit immediately so the browser's EventSource knows the connection is alive
    # and the user sees feedback before the slow network I/O begins.
    yield _sse_message(
        "connecting", {"message": f"Connecting to repository {owner}/{repo}…"}
    )
    await asyncio.sleep(0)  # flush to client before blocking

    # Stage 1: Load repo snapshot (network I/O — offload to thread)
    snapshot = await asyncio.to_thread(load_snapshot, owner, repo)
    yield _sse_message(
        "repo_loaded",
        {
            "message": "Repository loaded",
            "file_count": len(snapshot.files),
            "commit_sha": snapshot.commit_sha,
        },
    )
    await asyncio.sleep(0)

    # Stage 2: Chunk all files
    all_chunks = []
    for f in snapshot.files:
        all_chunks.extend(chunk_file(f.path, f.content))
    yield _sse_message(
        "chunked",
        {
            "message": "Files chunked",
            "chunk_count": len(all_chunks),
        },
    )
    await asyncio.sleep(0)

    # Stage 3: Extract signals (README headings, routes, entrypoints)
    readme_file = next(
        (f for f in snapshot.files if f.path.lower() in ("readme.md", "readme")), None
    )
    readme_md = readme_file.content if readme_file else ""
    signals = RepoSignals(
        readme_headings=extract_readme_signals(readme_md),
        routes=extract_route_signals(snapshot.files),
        entrypoints=extract_entrypoints(snapshot.files),
    )
    yield _sse_message(
        "signals_extracted",
        {
            "message": "Signals extracted",
            "headings": len(signals.readme_headings),
            "routes": len(signals.routes),
            "entrypoints": len(signals.entrypoints),
        },
    )
    await asyncio.sleep(0)

    yield _sse_message("features_proposed", {"message": "Features proposed"})
    await asyncio.sleep(0)
    yield _sse_message("pages_written", {"message": "Pages written"})
    await asyncio.sleep(0)
    yield _sse_message("done", {"message": "Complete"})


@router.get("/generate/stream")
async def generate_stream(
    repo_url: str = Query(..., description="Full GitHub repository URL"),
    _: None = Depends(require_api_key),
):
    """SSE endpoint that runs implemented pipeline stages and emits real progress events.
    LLM stages (features_proposed, pages_written) are stubs until Step 19."""

    async def event_gen():
        try:
            async for message in _run_pipeline(repo_url):
                yield message
        except Exception as exc:
            yield _sse_message("error", {"message": str(exc)})

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/generate", response_model=GenerateResponse)
def generate(body: GenerateRequest, _: None = Depends(require_api_key)):
    """Run the full wiki-generation pipeline and return the result."""
    try:
        return run_pipeline(str(body.repo_url))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
