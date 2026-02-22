# GitHub Wiki Generator

Automatic wiki generator for public GitHub repositories. Analyses repo code and produces user-facing feature documentation with inline source citations.

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

## Live URLs

| Service | URL |
|---------|-----|
| Backend | `https://wiki-generator-backend-ud74aktrjq-uc.a.run.app` |
| Frontend | `https://wiki-generator-frontend-254204084242.us-central1.run.app/` |

## Usage

1. Open the [frontend URL](https://wiki-generator-frontend-254204084242.us-central1.run.app/).
2. Paste any **public GitHub repository URL** into the input field (e.g. `https://github.com/browser-use/browser-use`).
3. Click **Generate Wiki**. A status bar streams live progress while the backend analyses the repo.
4. Once complete, the wiki renders with:
   - An **Overview** page (what the project does, architecture, quickstart)
   - **Feature pages** — one per user-facing feature, with inline citations linking to the exact source lines on GitHub
   - A **sidebar** for navigation between pages
5. Each citation link opens the relevant code on GitHub at the analysed commit SHA (stable, not `HEAD`).

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

**Required env vars** — defined in `.env` at the project root (gitignored):

```
BACKEND_API_KEY=<app auth key>
OPENAI_API_KEY=<openai key>
```

### Frontend

```bash
cd frontend
npm install
npm run dev    # http://localhost:3000
```

**Required env vars** (`frontend/.env.local`):

```
BACKEND_URL=http://localhost:8080
BACKEND_API_KEY=<same app auth key as backend>
```

## API

### `GET /health`
```json
{ "status": "healthy" }
```

### `POST /api/generate`
Headers: `x-api-key: <BACKEND_API_KEY>`

Request:
```json
{ "repo_url": "https://github.com/owner/repo" }
```

Response:
```json
{
  "repo_id": "owner/repo",
  "commit_sha": "<sha>",
  "overview_md": "...",
  "features": [
    { "id": "slug", "title": "...", "description": "...", "content_md": "..." }
  ]
}
```

## How It Works

The backend runs a deterministic multi-stage pipeline when a repo URL is submitted. Every stage feeds the next; no stage touches the LLM unless noted.

```
GitHub URL
    │
    ▼
 1. Parse URL          extract owner + repo from the URL
    │
    ▼
 2. Load Snapshot      fetch git tree + file contents via GitHub REST API
    │                  (pinned to the latest commit SHA)
    ▼
 3. Filter Files       drop binaries, generated files, build artefacts,
    │                  and files above the size limit
    ▼
 4. Extract Signals    scan files for README headings, HTTP route
    │                  definitions, and entry-point files — no LLM
    ▼
 5. Chunk Files        split every file into line-numbered text chunks
    │                  with stable IDs ("path:start-end")
    ▼
 6. Build Import Graph map file-to-file import relationships for
    │                  Python and JS/TS to enable evidence expansion
    ▼
 7. Build Search Index BM25 keyword index over all chunks for fast
    │                  per-feature retrieval
    ▼
 8. Propose Features ◆ LLM call — identify 5–9 user-facing features,
    │                  each with a title + seed file paths
    ▼
 9. Gather Evidence    per feature: seed files → import-graph expansion
    │                  → BM25 search → deduplicated bounded chunk pack
    ▼
10. Write Feature      ◆ LLM call per feature — generate markdown with
    Pages              inline citations; citations are converted to
    │                  stable GitHub permalink URLs (owner/repo/blob/SHA#Lx)
    ▼
11. Write Overview   ◆ LLM call — repo-level summary generated from
    Page               README + manifest files + entry points
    │
    ▼
12. Assemble           return GenerateResponse: commit SHA, overview
    Response           markdown, and list of feature pages
```

### Stage details

| # | Stage | Service | LLM? |
|---|-------|---------|------|
| 1 | Parse URL | `pipeline.py` | — |
| 2 | Load snapshot | `repo_loader.py` → GitHub REST API | — |
| 3 | Filter files | `file_filter.py` | — |
| 4 | Extract signals | `signals.py` (headings, routes, entrypoints) | — |
| 5 | Chunk files | `chunker.py` | — |
| 6 | Build import graph | `import_graph.py` (Python `import` + JS/TS `import`/`require`) | — |
| 7 | Build search index | `search_index.py` (BM25) | — |
| 8 | Propose features | `propose_features.py` | ✓ `gpt-4o-mini` |
| 9 | Gather evidence | `evidence.py` (seed → graph expand → BM25 → dedup) | — |
| 10 | Write feature pages | `write_pages.py` → `citations.py` (chunk ID → permalink) | ✓ `gpt-4o-mini` × N |
| 11 | Write overview | `write_pages.py` | ✓ `gpt-4o-mini` |
| 12 | Assemble response | `pipeline.py` | — |

### SSE streaming

Progress events are pushed to the browser via Server-Sent Events (`GET /api/generate/stream`) so users see live status updates as each stage completes. The full blocking `run_pipeline()` then runs via a normal `POST /api/generate` call once the stream signals `done`.

See [guide.md](guide.md) for the full execution spec.


## Challenge Notes

This project was built for the **cubic Coding Challenge** — a 48-hour sprint to build an automatic wiki generator for public GitHub repos.

### What I’d improve with more time

- **Live SSE pipeline** — the SSE stream currently stubs the LLM stages (feature proposals, page writing). Wiring the full `run_pipeline()` call into the stream would give real live progress for every stage instead of just repo-load and chunking.
- **Search / Q&A** across wiki pages — the bonus feature from the spec; a BM25 or embedding search over generated pages would be straightforward given the existing `SearchIndex` infrastructure.
- **Better error UX** — surface rate-limit, private-repo, and timeout errors with actionable messages instead of generic failure states.
- **Caching** — cache generated wikis by `(owner, repo, commit_sha)` in Cloud Firestore or Redis so repeat requests are instantly served.
- **Streaming LLM responses** — pipe OpenAI stream tokens through SSE so users see text appearing rather than waiting for each page to fully complete.

### What isn’t production-ready

- **No rate limiting** on the `/api/generate` endpoint — a single request triggers 10+ LLM calls and GitHub API fetches; without throttling this is DoS-able.
- **No request queuing** — concurrent generate requests will compete for OpenAI quota and GitHub rate limits.
- **Single Cloud Run instance** — the backend is stateless but cold-start latency (2–4 s) would need a min-instances setting for production traffic.
- **LLM output quality** — citations can hallucinate line ranges that are adjacent but not exact; a post-processing verification step against the actual source lines would improve trust.
- **No tests for the full live pipeline** — all LLM calls are mocked in tests; a lightweight integration test against a small known repo would catch prompt-regressions.

## Deployment

```bash
# Backend
gcloud run deploy wiki-generator-backend \
  --project pushstart-481717 \
  --source ./backend \
  --region us-central1 \
  --allow-unauthenticated

# Check CI
GH_PAGER=cat gh run list --repo gtpooniwala/githubWikiGenerator
```

## GCP Config

- Project: `pushstart-481717`
- Region: `us-central1`
- WIF Pool: `github-pool` / Provider: `github-provider`
