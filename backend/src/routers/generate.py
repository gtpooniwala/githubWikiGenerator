import asyncio
import json
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from auth import require_api_key
from models.schemas import GenerateRequest, GenerateResponse
from services import chunker as chunker_mod
from services import import_graph as import_graph_mod
from services.evidence import gather_all_evidence
from services.pipeline import run_pipeline
from services.propose_features import propose_features
from services.repo_loader import load_snapshot
from services.search_index import SearchIndex
from services.signals import (
    RepoSignals,
    extract_entrypoints,
    extract_readme_signals,
    extract_route_signals,
)
from services.write_pages import write_all_feature_pages, write_overview_page

router = APIRouter(prefix="/api")

# Files whose raw content must be kept in memory through the LLM stages so
# write_overview_page() can read them.  All other file content is freed after
# chunking to reduce peak memory usage.
_OVERVIEW_KEEP_CONTENT: frozenset[str] = frozenset(
    {
        "readme.md",
        "readme.rst",
        "readme.txt",
        "readme",
        "package.json",
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "requirements.txt",
        "cargo.toml",
        "go.mod",
        "main.py",
        "__main__.py",
        "app.py",
        "server.py",
        "index.ts",
        "index.js",
        "index.tsx",
        "main.ts",
        "app.ts",
        "wsgi.py",
        "asgi.py",
    }
)

# How often (seconds) to write an SSE keepalive comment while a blocking
# thread is running.  This prevents Cloud Run / intermediate proxies from
# closing an idle stream connection.
_KEEPALIVE_INTERVAL: float = 15.0


def _sse_message(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# SSE comment — browsers ignore it but it keeps the TCP connection alive.
_SSE_KEEPALIVE = ": keepalive\n\n"


def _parse_repo_id(repo_url: str) -> str:
    """Extract 'owner/repo' from a GitHub URL."""
    url = str(repo_url).removesuffix("/").removesuffix(".git").removesuffix("/")
    parts = url.split("github.com/")
    if len(parts) != 2:
        raise ValueError(f"Cannot parse repo_id from URL: {repo_url}")
    return parts[1]


async def _run_pipeline(repo_url: str) -> AsyncIterator[str]:
    """Run the full pipeline, yielding SSE messages + keepalives.

    Uses a producer-consumer queue so that a background keepalive task can
    push SSE comment lines (``': keepalive'``) into the stream while any
    blocking thread (LLM call, file fetch, etc.) is executing.  Without
    this, Cloud Run / intermediate HTTP proxies may close an idle connection
    before the blocking call finishes.

    The final ``done`` event carries the complete :class:`GenerateResponse`
    payload so the browser can render the wiki without a second round-trip.
    """
    # Sentinel value that signals the pipeline has finished.
    _DONE_SENTINEL: str | None = None

    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def _pipeline_worker() -> None:
        """Background task: run all pipeline stages, posting to *queue*."""
        # Keepalive pump — runs concurrently during every blocking call.
        _ka_active = True

        async def _keepalive_pump() -> None:
            while _ka_active:
                await asyncio.sleep(_KEEPALIVE_INTERVAL)
                if _ka_active:
                    await queue.put(_SSE_KEEPALIVE)

        ka_task = asyncio.create_task(_keepalive_pump())
        try:
            await _pipeline_stages(repo_url, queue)
        except Exception as exc:
            await queue.put(_sse_message("error", {"message": str(exc)}))
        finally:
            _ka_active = False
            ka_task.cancel()
            try:
                await ka_task
            except asyncio.CancelledError:
                pass
            await queue.put(_DONE_SENTINEL)

    task = asyncio.create_task(_pipeline_worker())
    try:
        while True:
            item = await queue.get()
            if item is _DONE_SENTINEL:
                break
            yield item
    finally:
        if not task.done():
            task.cancel()


async def _pipeline_stages(repo_url: str, queue: asyncio.Queue) -> None:
    """Execute all pipeline stages and post SSE messages to *queue*."""
    repo_id = _parse_repo_id(repo_url)
    owner, repo = repo_id.split("/", 1)

    # Emit immediately so the browser knows the connection is alive before the
    # first blocking network call.
    await queue.put(
        _sse_message("connecting", {"message": f"Connecting to repository {owner}/{repo}…"})
    )

    # ------------------------------------------------------------------
    # Stage 1: Load repo snapshot (parallel network I/O)
    # ------------------------------------------------------------------
    snapshot = await asyncio.to_thread(load_snapshot, owner, repo)
    await queue.put(_sse_message(
        "repo_loaded",
        {
            "message": "Repository loaded",
            "file_count": len(snapshot.files),
            "commit_sha": snapshot.commit_sha,
        },
    ))

    # ------------------------------------------------------------------
    # Stage 2: Extract signals (README headings, HTTP routes, entry points)
    # ------------------------------------------------------------------
    readme_headings = (
        extract_readme_signals(snapshot.readme.content) if snapshot.readme else []
    )
    routes = extract_route_signals(snapshot.files)
    entrypoints = extract_entrypoints(snapshot.files)
    signals = RepoSignals(
        readme_headings=readme_headings,
        routes=routes,
        entrypoints=entrypoints,
    )
    await queue.put(_sse_message(
        "signals_extracted",
        {
            "message": "Signals extracted",
            "headings": len(signals.readme_headings),
            "routes": len(signals.routes),
            "entrypoints": len(signals.entrypoints),
        },
    ))

    # ------------------------------------------------------------------
    # Stage 3: Chunk all files
    # ------------------------------------------------------------------
    all_chunks = []
    for f in snapshot.files:
        all_chunks.extend(chunker_mod.chunk_file(f.path, f.content))
    await queue.put(_sse_message(
        "chunked",
        {
            "message": "Files chunked",
            "chunk_count": len(all_chunks),
        },
    ))

    # ------------------------------------------------------------------
    # Stage 4: Build import graph (CPU-bound)
    # ------------------------------------------------------------------
    import_graph = await asyncio.to_thread(
        import_graph_mod.build_import_graph, snapshot.files
    )
    edge_count = sum(len(v) for v in import_graph.values())
    await queue.put(_sse_message(
        "import_graph_built",
        {
            "message": "Import graph built",
            "edges": edge_count,
        },
    ))

    # Free raw file content that is not needed by write_overview_page() —
    # chunks hold all the text required for LLM stages.
    for fe in snapshot.files:
        if fe.path.rsplit("/", 1)[-1].lower() not in _OVERVIEW_KEEP_CONTENT:
            fe.content = ""

    # ------------------------------------------------------------------
    # Stage 5: Build BM25 search index
    # ------------------------------------------------------------------
    search_index = SearchIndex()
    search_index.add_chunks(all_chunks)
    await queue.put(_sse_message(
        "search_index_built",
        {
            "message": "Search index built",
            "indexed_chunks": len(all_chunks),
        },
    ))

    # ------------------------------------------------------------------
    # Stage 6: Propose features (LLM)
    # ------------------------------------------------------------------
    proposal = await asyncio.to_thread(propose_features, snapshot, signals)
    features = proposal.features
    await queue.put(_sse_message(
        "features_proposed",
        {
            "message": f"{len(features)} features identified",
            "features": [{"id": f.id, "title": f.title} for f in features],
        },
    ))

    # ------------------------------------------------------------------
    # Stage 7: Gather evidence (seed → import-graph expand → BM25 → dedup)
    # ------------------------------------------------------------------
    packs = await asyncio.to_thread(
        gather_all_evidence, features, all_chunks, import_graph, search_index
    )
    await queue.put(_sse_message(
        "evidence_gathered",
        {
            "message": "Evidence gathered",
            "feature_count": len(packs),
        },
    ))

    # ------------------------------------------------------------------
    # Stage 8: Write feature pages (LLM × N)
    # ------------------------------------------------------------------
    wiki_features = await asyncio.to_thread(
        write_all_feature_pages,
        features,
        packs,
        owner=owner,
        repo=repo,
        commit_sha=snapshot.commit_sha,
    )
    await queue.put(_sse_message(
        "pages_written",
        {
            "message": f"{len(wiki_features)} feature pages written",
        },
    ))

    # ------------------------------------------------------------------
    # Stage 9: Write overview page (LLM)
    # ------------------------------------------------------------------
    overview_md = await asyncio.to_thread(
        write_overview_page,
        snapshot,
        owner=owner,
        repo=repo,
        commit_sha=snapshot.commit_sha,
    )
    await queue.put(_sse_message(
        "overview_written",
        {
            "message": "Overview page written",
        },
    ))

    # ------------------------------------------------------------------
    # Stage 10: Assemble and return — full payload in the done event
    # ------------------------------------------------------------------
    response = GenerateResponse(
        repo_id=f"{owner}/{repo}",
        commit_sha=snapshot.commit_sha,
        overview_md=overview_md,
        features=wiki_features,
    )
    await queue.put(_sse_message("done", response.model_dump()))


@router.get("/generate/stream")
async def generate_stream(
    repo_url: str = Query(..., description="Full GitHub repository URL"),
    _: None = Depends(require_api_key),
):
    """SSE endpoint — runs the full pipeline and streams real progress events.

    Every pipeline stage emits an event when it completes.  The final ``done``
    event payload is the complete ``GenerateResponse`` JSON so the browser can
    render the wiki without a second round-trip.
    """

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
