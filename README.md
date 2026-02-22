# GitHub Wiki Generator

Automatic wiki generator for public GitHub repositories. Analyses repo code and produces user-facing feature documentation with inline source citations.

---

## Usage — Try the Live Demo

The app is fully deployed and ready to use. No setup required.

**[Open the frontend](https://wiki-generator-frontend-254204084242.us-central1.run.app/)**

1. The page may take **a few seconds to load** on first visit while the frontend and backend warm up. A health-check runs automatically — wait for it to show a green "healthy" status before proceeding.
2. Paste any **public GitHub repository URL** into the input box, or select one of the pre-filled examples.
3. Click **Generate Wiki**.
4. Watch live progress as the pipeline runs. Wiki generation typically completes in **a few minutes for small/medium repos; larger repos may take longer**.
5. Once the wiki appears, use the **Ask the wiki** panel at the bottom of the content area to ask questions about the repository — the entire generated wiki is used as context for each answer.

The output includes an **Overview page** (what the project does, architecture, quickstart) and a set of **Feature pages** — one per user-facing feature, each with inline citations that link to the exact source lines on GitHub at the analysed commit SHA.

> **Note on architecture:** The backend is separate from the frontend and requires an API key to call directly.

**Troubleshooting**

- **Slow initial load / health check stuck:** Cloud Run services spin down after inactivity. Wait up to 30 seconds on first visit; the health indicator will turn green once the backend is warm.
- **Wiki generation stalls or errors:** Try a smaller or simpler repo first to confirm the pipeline is working. If the issue persists across multiple repos, the backend may be hitting an API quota limit — try again in a few minutes.
- **Generation takes over 10 minutes:** Something has gone wrong. Refresh and try a different repo, or raise an issue on the repository.

---


## Architecture

| Layer | Tech | Deployed |
|-------|------|---------|
| Frontend | Next.js (App Router, TypeScript) | Cloud Run |
| Backend | FastAPI (Python 3.12) | Cloud Run |
| LLM | OpenAI (`gpt-5-mini`) | backend-only |
| CI/CD | GitHub Actions + Workload Identity Federation | — |

```
.
├── backend/          # FastAPI — core pipeline logic
├── frontend/         # Next.js — UI + proxy routes
└── .github/workflows/
    ├── test.yml
    ├── deploy-backend.yml
    └── deploy-frontend.yml
```

## Live URL

| Service | URL |
|---------|-----|
| Frontend | `https://wiki-generator-frontend-254204084242.us-central1.run.app/` |

## Local Development

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# Run tests
.venv/bin/python -m pytest -q

# Run server
uvicorn main:app --reload --port 8080 --app-dir src
```

**Required env vars** — single `.env` file at the project root (used by both backend and frontend locally):

```
BACKEND_API_KEY=<app auth key>
OPENAI_API_KEY=<openai key>
BACKEND_URL=http://localhost:8080
```

The frontend reads `BACKEND_URL` and `BACKEND_API_KEY` from this file via Next.js's built-in `.env` loading.

### Frontend

```bash
cd frontend
npm install
npm run dev    # http://localhost:3000
```

## API

All backend endpoints are behind `x-api-key: <BACKEND_API_KEY>`. The frontend proxies each one via Next.js route handlers under `frontend/src/app/api/`.

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check — `{ "status": "healthy" }` |
| `/api/generate` | POST | Run full pipeline, return `GenerateResponse` |
| `/api/generate/stream` | GET (SSE) | Run pipeline, stream stage events, `done` carries full payload |
| `/api/qa` | POST | Answer a question using the generated wiki as context |

Full request/response schemas, SSE event shapes, and auth patterns are in [guide.md](guide.md).

## How It Works

The backend runs a deterministic multi-stage pipeline when a repo URL is submitted. Every stage feeds the next; no stage makes LLM calls unless noted.

```
GitHub URL
    │
    ▼
 1. Load Snapshot      fetch git tree + file contents via GitHub REST API;
    │                  filter out binaries, build artefacts, and oversized
    │                  files; pin everything to the latest commit SHA
    ▼
 2. Extract Signals    scan files for README headings, HTTP route
    │                  definitions, and entry-point indicators — no LLM
    ▼
 3. Chunk Files        split every file into line-numbered text chunks
    │                  with stable IDs ("path:start-end")
    ▼
 4. Build Import Graph map file-to-file import relationships for
    │                  Python and JS/TS to enable evidence expansion
    ▼
 5. Build Search Index BM25 keyword index over all chunks for fast
    │                  per-feature retrieval
    ▼
 6. Propose Features ◆ LLM call — identify 5–9 user-facing features,
    │                  each with a title + seed file paths
    ▼
 7. Gather Evidence    per feature: seed files → import-graph expansion
    │                  → BM25 search → deduplicated bounded chunk pack
    ▼
 8. Write Feature      ◆ LLM call per feature — generate markdown with
    Pages              inline citations; citations are converted to
    │                  stable GitHub permalink URLs (owner/repo/blob/SHA#Lx)
    ▼
 9. Write Overview   ◆ LLM call — repo-level summary generated from
    Page               README + manifest files + entry points
    │
    ▼
    Assemble           return GenerateResponse: commit SHA, overview
    Response           markdown, and list of feature pages
```

### Stage details

| # | Stage | Service | LLM? |
|---|-------|---------|------|
| 1 | Load snapshot | `repo_loader.py` → GitHub REST API (filtered by `file_filter.py`) | — |
| 2 | Extract signals | `signals.py` (headings, routes, entrypoints) | — |
| 3 | Chunk files | `chunker.py` | — |
| 4 | Build import graph | `import_graph.py` (Python `import` + JS/TS `import`/`require`) | — |
| 5 | Build search index | `search_index.py` (BM25) | — |
| 6 | Propose features | `propose_features.py` | ✓ `gpt-5-mini` |
| 7 | Gather evidence | `evidence.py` (seed → graph expand → BM25 → dedup) | — |
| 8 | Write feature pages | `write_pages.py` → `citations.py` (chunk ID → permalink) | ✓ `gpt-5-mini` |
| 9 | Write overview | `write_pages.py` | ✓ `gpt-5-mini` |

### SSE streaming

All nine pipeline stages run inside the SSE generator (`GET /api/generate/stream`). The browser receives a named event as each stage completes:

| Event | Stage |
|---|---|
| `connecting` | Connection established |
| `repo_loaded` | Snapshot fetched (file count + commit SHA) |
| `signals_extracted` | README headings / routes / entry points |
| `chunked` | File chunking complete |
| `import_graph_built` | Import-graph edges counted |
| `search_index_built` | BM25 index ready |
| `features_proposed` | LLM identified N features (with titles) |
| `evidence_gathered` | Evidence packs assembled |
| `pages_written` | Feature pages written |
| `overview_written` | Overview page written |
| `done` | **Full `GenerateResponse` JSON as the event payload** |

The frontend reads the `done` payload directly — no second `POST /api/generate` round-trip.

See [guide.md](guide.md) for full schemas, SSE event payloads, and local dev details.
For architectural tradeoffs and planned retrieval/chunking upgrades, see [pipeline-improvements.md](pipeline-improvements.md).

---

## Where to look in the code

- **Pipeline orchestrator:** `backend/src/services/pipeline.py` — `run_pipeline()` wires all 9 stages end-to-end
- **Evidence gathering:** `backend/src/services/evidence.py` — seed files → import-graph BFS → BM25 search → bounded dedup
- **Page writing + citations:** `backend/src/services/write_pages.py` + `backend/src/services/citations.py` — LLM drafts pages, `[path:start-end]` IDs are resolved to GitHub permalink URLs
- **SSE streaming:** `backend/src/routers/generate.py` — `_pipeline_stages()` posts to a queue; keepalive task prevents proxy timeouts
- **Frontend rendering:** `frontend/src/app/page.tsx` (SSE consumer + router) and `frontend/src/components/WikiViewer.tsx` (tabbed wiki + Q&A panel)
- **Auth middleware:** `backend/src/auth.py` + `backend/src/config.py`
- **CI/CD:** `.github/workflows/test.yml`, `deploy-backend.yml`, `deploy-frontend.yml`

## Design Choices

- **Feature-first organisation** — output is structured around user-facing features, not code layers. This forces the LLM to reason about intent rather than implementation topology. See [pipeline-improvements.md](pipeline-improvements.md) for the tradeoffs in how features are proposed.
- **Deterministic retrieval before any LLM call** — evidence is assembled via BM25 + import-graph traversal with stable, bounded chunk IDs anchored to a single commit SHA. The LLM only writes; it doesn't retrieve. See [pipeline-improvements.md](pipeline-improvements.md) for audit and planned improvements.
- **SSE-first, no polling** — the pipeline runs entirely inside the SSE generator; the `done` event carries the full wiki payload so the frontend needs no second round-trip. See [guide.md](guide.md) for the event sequence.

## Challenge Notes

This project was built for the **cubic Coding Challenge** — a 48-hour sprint to build an automatic wiki generator for public GitHub repos.

Detailed rationale and alternatives for pipeline quality improvements are documented in [pipeline-improvements.md](pipeline-improvements.md).

### What I’d improve with more time

- **Pipeline logic improvements** - [pipeline-improvements.md](pipeline-improvements.md).
- **Parallel feature page writing** — feature pages are written sequentially; all evidence packs are independent so this is trivially parallelisable with a thread pool, cutting LLM wall-clock time from ~N×4s to ~4s regardless of feature count.
- **Caching and persistence** — no caching keyed by `(repo, commit_sha)` exists today; repeat requests re-run the full pipeline. A simple store (even SQLite) would make re-visits instant and enable a “Regenerate” flow.
- **Testing coverage and evaluation harness** — all LLM calls are mocked in tests; there is no integration test against a live repo or benchmark set to catch prompt regressions or measure citation quality. See [pipeline-improvements.md](pipeline-improvements.md) for a proposed evaluation approach.
- **LLM evaluation and prompt iteration** — while the current prompts produce decent output, there is ample room for improvement in clarity, formatting, and citation quality. A more rigorous evaluation setup would enable systematic prompt tuning.

### Bonus features implemented

- **Q&A across the wiki** — an “Ask the wiki” panel lives in the sidebar of every wiki page. The full generated wiki (overview + all feature pages, typically 3–8k tokens) is passed as context to a single `gpt-5-mini` call, giving the model cross-page awareness. No retrieval step is needed at this scale.

### What isn’t production-ready

- **No rate limiting or request queuing** on `/api/generate` — a single request triggers ~10 LLM calls and multiple GitHub API fetches; without throttling, concurrent requests compete for quota and the endpoint is DoS-able.
- **Single Cloud Run instance** — the backend is stateless but would need a `min-instances` setting and autoscaling config for production traffic.
- **Limited repo coverage** — tested against a handful of small-to-medium repos. Larger or unusual codebases may hit edge cases in the chunker, import graph, or evidence gatherer.
