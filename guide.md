# GitHub Wiki Generator – Build Log

This repo was built using a structured AI-assisted workflow. A detailed implementation spec was written upfront, then executed step-by-step with an AI coding agent. This document is a record of that process — including the original architecture decisions, API contract, and a chronological log of every build step.

---

## What Was Built

A deployed web app that generates a navigable, cited wiki for any public GitHub repository. Users enter a repo URL; the app fetches the code, runs a multi-stage analysis pipeline (chunking, signals extraction, LLM feature proposals, evidence gathering, page writing), and streams live progress updates before rendering the final wiki.

**Live:**
- Frontend: `https://wiki-generator-frontend-254204084242.us-central1.run.app`
- Backend: deployed separately on Cloud Run; not exposed publicly (requires API key)

---

## Tech Stack

| Layer              | Choice                                                      |
|--------------------|-------------------------------------------------------------|
| Frontend           | Next.js (TypeScript, App Router), deployed to GCP Cloud Run |
| Backend            | FastAPI (Python), deployed to GCP Cloud Run                 |
| LLM                | OpenAI SDK (`gpt-5-mini`; backend-only)                    |
| Repo fetch         | GitHub REST API (optional token for higher rate limits)     |
| Backend tests      | pytest + respx + pytest-asyncio                             |
| Frontend tests     | Vitest + React Testing Library                              |
| CI/CD              | GitHub Actions + Workload Identity Federation               |

---

## Build Steps

Each step was implemented atomically: code written, tests passing locally, committed, deployed, smoke-checked before moving on.

| Step | Name | Commit | Notes |
|------|------|--------|-------|
| 1 | Repo hygiene + Docker context | `4743029` | `.gitignore`, `.dockerignore`, secrets purged |
| 2 | Backend venv + pytest harness | `d085283` | `requirements.txt`, `requirements-dev.txt`, `pytest.ini` |
| 3 | Config + auth middleware | `f685a42` | `config.py`, `auth.py`, `BACKEND_API_KEY` on `/api/generate` |
| 4 | Canonical schemas | `d06a905` | `models/schemas.py` — `GenerateRequest`, `WikiFeature`, `GenerateResponse` |
| 5 | GitHub repo snapshot | `764a1f8` | `github_client.py`, `file_filter.py`, `repo_loader.py` |
| 6 | Chunker | `3bf53cb` | `chunker.py` — semantic + sliding window, line-numbered |
| 7 | Signals extraction | `4caff95` | `signals.py` — README, routes, entrypoints (no LLM) |
| 7a | Bug-fix pass (Steps 1–7) | `bc154ec` | `_parse_repo_id` fix; CI deploy URL; auth fixes |
| 8 | Frontend proxy + Vitest | `5afdbc6` | `api/generate/route.ts`, `vitest.config.ts`, 7 frontend tests |
| 9 | Frontend UI MVP | `60bff50` | `RepoForm`, `WikiViewer`, `Markdown` components; 10 UI tests |
| 10 | Real-time SSE status | `91d51d0` | SSE stream from backend; `EventSource` in frontend; 10+6 new tests |
| 11 | File-level import graph | `544d4c1` | `import_graph.py` — Python + JS/TS; 22 tests |
| 12 | Search index over chunks | `0627c74` | `search_index.py` — BM25 + substring fallback; 24 tests |
| 13 | LLM client | `f9e7917` | `llm.py` — `chat_text`, `chat_json`, fence-strip, retries; 27 tests |
| 14 | Feature proposals | `4645e1b` | `propose_features.py` — LLM-driven, banned-word filter, slug normalisation; 31 tests |
| 15 | Evidence gathering | `0bee742` | `evidence.py` — seed → import-graph BFS → search hits, dedup, bounded; 24 tests |
| 16 | Page writing + citations | `d5b4b2a` | `citations.py` + `write_pages.py` — `[path:start-end]` → GitHub permalink links; 38 tests |
| 17 | Overview page | `5278916` | `write_overview_page()` — README + manifests + entrypoints evidence; 263 total tests |
| 18 | Pipeline orchestrator | `8259cc5` | `pipeline.py` — `run_pipeline()` wires all stages; 21 smoke tests; 284 total |
| 19 | Wire `/api/generate` endpoint | `5e613e4` | `routers/generate.py` calls `run_pipeline()`; auth + schema tests |
| 20 | Frontend navigable wiki | `ba327e7` | `WikiViewer` after SSE+POST; `/wiki/[owner]/[repo]` page; 28 frontend tests |
| 21 | CI tests gate deploy | `ae80e65` | `test.yml`; deploy workflows `needs: test` |
| 22 | Deploy + smoke checks | `029abb8` | All CI green; both Cloud Run services healthy |
| 23 | Polish | `8b5a517` | Memory cleanup in pipeline; README usage + reflection sections |
| — | Q&A feature | `bbff2b9` | `POST /api/qa` + Ask the Wiki panel in sidebar; 11 backend + 9 frontend tests |
| — | SSE error handling | `97de00d` | `onerror` always sets error state; better connection-error messaging |
| — | Full-height wiki + collapsible log | `edd88c5` | UX: sidebar Q&A, collapsible SSE log, full-height layout |
| — | Rate-limit safety | `4a733c3` | Parallel file fetch; SSE keepalive; Cloud Run timeout 600s / memory 1Gi |
| — | 429 retry + quota check | `4a23332` | Retry on OpenAI 429; proactive quota check; workers 10→5 |
| — | UI polish | `c163d3a` | Step numbers in status panel, details drawer, removed rainbow colors |

**Final test count:** 284 backend + 28 frontend tests passing.

---

## Architecture

### Backend (`backend/src/`)

```
main.py           # FastAPI app entry point; uvicorn main:app --host 0.0.0.0 --port 8080
config.py         # Reads BACKEND_API_KEY, OPENAI_API_KEY as module-level constants
auth.py           # require_api_key() FastAPI dependency
models/
  schemas.py        # GenerateRequest, WikiFeature, GenerateResponse
  llm_schemas.py    # FeatureProposalList, EvidenceSelection, WikiPageDraft
  repo_snapshot.py  # RepoSnapshot, FileEntry
routers/
  health.py         # GET /health
  generate.py       # POST /api/generate + GET /api/generate/stream (SSE)
  qa.py             # POST /api/qa
services/
  github_client.py  # get_repo, get_branch_sha, get_tree, get_file (httpx; GITHUB_TOKEN optional)
  file_filter.py    # should_include(path, size_bytes, is_binary_guess) -> bool
  repo_loader.py    # load_snapshot(owner, repo) -> RepoSnapshot
  chunker.py        # chunk_file(path, content) -> list[Chunk]; semantic + sliding window
  signals.py        # extract_readme_signals, extract_route_signals, extract_entrypoints
  import_graph.py   # build_import_graph(files) -> dict[str, list[str]] — Python + JS/TS
  search_index.py   # SearchIndex.from_chunks(chunks); BM25 + substring fallback
  llm.py            # chat_text(), chat_json(schema) — OpenAI wrapper with retries
  propose_features.py  # propose_features(snapshot, signals) -> FeatureProposalList
  evidence.py       # gather_evidence(feature, ...) -> EvidencePack; gather_all_evidence()
  citations.py      # resolve_citations(md, owner, repo, sha) — [path:start-end] → GitHub permalink links
  write_pages.py    # write_feature_page(), write_overview_page(), write_all_feature_pages()
  pipeline.py       # run_pipeline(owner, repo) — wires all stages end-to-end
```

`PYTHONPATH=/app/src` in Dockerfile; `pythonpath = src` in `pytest.ini`.

### Pipeline Stages (SSE stream order)

`connecting` (connection event) → `repo_loaded` → `signals_extracted` → `chunked` → `import_graph_built` → `search_index_built` → `features_proposed` → `evidence_gathered` → `pages_written` → `overview_written` → `done` (terminal event, carries full `GenerateResponse`)

`GET /api/generate/stream?repo_url=<url>` streams `text/event-stream`; each `data:` payload is JSON `{ "message": "...", ...stage fields }`. The Next.js proxy at `frontend/src/app/api/generate/stream/route.ts` forwards the `repo_url` param and `x-api-key` header. The browser `EventSource` in `page.tsx` renders live status + the final wiki on `done`.

### Frontend (`frontend/src/`)

```
app/
  page.tsx                        # Home — RepoForm + SSE consumer + WikiViewer
  layout.tsx
  api/
    health/route.ts               # Proxy → backend /health
    generate/route.ts             # Proxy → backend POST /api/generate
    generate/stream/route.ts      # Proxy → backend GET /api/generate/stream
    qa/route.ts                   # Proxy → backend POST /api/qa
  wiki/[owner]/[repo]/page.tsx    # Standalone wiki page (deep-link)
components/
  RepoForm.tsx
  WikiViewer.tsx                  # Tabbed sidebar: features + Q&A panel
  Markdown.tsx
lib/
  api.ts
```

---

## API Contract

### Backend

**`GET /health`**
- 200: `{ "status": "healthy" }`

**`POST /api/generate`**
- Headers: `x-api-key: <BACKEND_API_KEY>`
- Body: `{ "repo_url": "https://github.com/owner/repo" }`
- Response:
  ```json
  {
    "repo_id": "owner/repo",
    "commit_sha": "<sha>",
    "overview_md": "...",
    "features": [
      { "id": "feature-slug", "title": "...", "description": "...", "content_md": "..." }
    ]
  }
  ```

**`GET /api/generate/stream?repo_url=<url>`**
- Headers: `x-api-key: <BACKEND_API_KEY>`
- SSE stream of named events (see Pipeline Stages above)
- Final `done` event carries the full `GenerateResponse` payload

**`POST /api/qa`**
- Headers: `x-api-key: <BACKEND_API_KEY>`
- Body: `{ "repo_id": "owner/repo", "question": "...", "overview_md": "...", "features": [...] }`
- Response: `{ "answer": "..." }`

### Frontend proxies (Next.js route handlers)

- `GET /api/health` → `${BACKEND_URL}/health`
- `POST /api/generate` → `${BACKEND_URL}/api/generate` (forwards `x-api-key`)
- `GET /api/generate/stream` → `${BACKEND_URL}/api/generate/stream` (forwards `x-api-key`)
- `POST /api/qa` → `${BACKEND_URL}/api/qa` (forwards `x-api-key`)

`OPENAI_API_KEY` is backend-only and never exposed to the client.

---

## Developer Reference

### Environment Variables

| Variable | Where | Notes |
|----------|-------|-------|
| `BACKEND_API_KEY` | Backend Cloud Run + local `.env` | App-level auth key; no hardcoded default — if unset, all auth fails |
| `OPENAI_API_KEY` | Backend Cloud Run + local `.env` | Never expose to frontend |
| `GITHUB_TOKEN` | Backend Cloud Run + local `.env` | Optional; raises rate limit from 60 → 5000 req/hr |
| `BACKEND_URL` | Frontend Cloud Run + local `.env` | Points frontend proxy to backend service URL |

### Running Tests

```bash
# Backend
cd backend
.venv/bin/python -m pytest -q

# Frontend
cd frontend
npx vitest run
```

Always use `.venv/bin/python -m pytest` — not bare `pytest` — to avoid PATH issues.

### Key Test Patterns

**Backend auth** — `config.API_KEY` is a module-level constant (cached at import time). `monkeypatch.setenv` does not work. Always use:
```python
monkeypatch.setattr(config, "API_KEY", "test-key")
```

**LLM mocking** — `services/llm.py` holds a module-level `_client`. Inject a mock and always reset in teardown:
```python
from services.llm import _set_client
_set_client(_mock_client("...json..."))
# ... test ...
_set_client(None)
```
Patch `services.llm.time.sleep` to keep retry tests instant. Never call real OpenAI in tests.

**respx fixtures** — use `assert_all_called=False`; this is intentional, not a workaround.

### Deployment

```bash
# Deploy backend
gcloud run deploy wiki-generator-backend \
  --project pushstart-481717 --source ./backend \
  --region us-central1 --allow-unauthenticated

# Deploy frontend
gcloud run deploy wiki-generator-frontend \
  --project pushstart-481717 --source ./frontend \
  --region us-central1 --allow-unauthenticated

# Check CI runs
GH_PAGER=cat gh run list --repo gtpooniwala/githubWikiGenerator

# Tail backend logs
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=wiki-generator-backend" \
  --project pushstart-481717 --limit 20 --format "table(timestamp,textPayload)"
```

**GCP project:** `pushstart-481717`, region `us-central1`
**CI/CD:** GitHub Actions with Workload Identity Federation. Both deploy workflows gate on `needs: test` (backend pytest + frontend vitest + build must pass).


