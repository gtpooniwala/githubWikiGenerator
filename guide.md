# GitHub Wiki Generator – **Agent-Execution Implementation Guide **

This is aN **execution-spec for agentic coding**.

It is aligned to the **current architecture**`:

* **Frontend:** Next.js (App Router, TypeScript) deployed to **GCP Cloud Run** (Docker container)
* **Backend:** FastAPI (Python) deployed to **GCP Cloud Run** (Docker container)
* **Core logic lives in backend** (repo fetch → analysis → LLM calls → wiki assembly)
* **CI/CD:** GitHub Actions (Workload Identity Federation) deploys both services on push
* Frontend contains a Next.js route handler `/api/health` that proxies to `${BACKEND_URL}/health` and the homepage currently does health checks (warm-up behavior). Use this pattern in the final product.

---

## Project Overview

**Goal:** Build an automatic Wiki Generator for public GitHub repositories that organizes documentation by **user-facing features** (not technical layers) with **inline citations** linking back to source code.

**Final Deliverable:** A deployed web app where users can input a GitHub repo URL and get a navigable wiki with cited documentation.

---

## ⚠️ Collaborative Workflow (Strict)

### How to Work

For each step:

0. Focus on one step at a time. Avoid jumping ahead, making assumptions or making plans about future steps.
1. Implement exactly the tasks listed. If there is a problem with the instructions or you think of a better way to do something, pause execution and ask for clarification before proceeding. Do not make unilateral decisions that deviate from the spec without approval.
2. Run tests locally.
3. Report:

   * What was built
   * Key decisions
   * Tests run + results
   * Any issues/concerns
4. Wait for approval.
5. After approval:

   * Commit with the template below
   * Push
   * Verify CI passed and Cloud Run deploy succeeded

### Definition of “Done” for any step

A step is only complete when:

1. **All tests pass** (local + CI where applicable)
2. **You approve** the changes
3. Changes are **committed**
4. **Deployment succeeds** (Cloud Run revision healthy + smoke checks)
5. You update the “Current Status” section in this doc with a brief summary of what was done and any known issues.

### Commit Message Template

```
Step X: <short name>

## What changed
- ...

## Tests
- backend: ...
- frontend: ...

## Deploy
- backend revision: ...
- frontend revision: ...
- smoke checks: ...
```

### Important Rules (Agentic)

* Don’t invent API contracts or data structures: follow this doc.
* Write tests as you go (unit tests before integrating LLM calls).
* Prefer deterministic logic and fixtures; isolate LLM calls behind an interface.
* Any time `.gitignore` / `.dockerignore` needs change, update it immediately.

---

## Current Status

### Steps Complete ✅

| Step | Name | Commit | Notes |
|------|------|--------|-------|
| 1 | Repo hygiene + Docker context | `4743029` | `.gitignore`, `.dockerignore`, `gcp-key.json` removed |
| 2 | Backend venv + pytest harness | `d085283` | `requirements.txt`, `requirements-dev.txt`, `pytest.ini` |
| 3 | Config + auth middleware | `f685a42` | `src/config.py`, `src/auth.py`, auth on `/api/generate` |
| 4 | Canonical schemas | `d06a905` | `src/models/schemas.py`, Dockerfile fixed |
| 5 | GitHub repo snapshot | `764a1f8` | `services/github_client.py`, `file_filter.py`, `repo_loader.py` |
| 6 | Chunker | `3bf53cb` | `services/chunker.py` — semantic + sliding window |
| 7 | Signals extraction | `4caff95` | `services/signals.py` — README, routes, entrypoints |
| 7a | Bug-fix pass (Steps 1–7) | `bc154ec` | `_parse_repo_id` rstrip→removesuffix; CI deploy URL fix; `GenerateResponse` type fix; `--allow-unauthenticated` added to both CI workflows |
| 8 | Frontend proxy route + Vitest | `5afdbc6` | `vitest.config.ts`, `vitest.setup.ts`, `tests/route-generate.test.ts` — 7 frontend tests |
| 9 | Frontend UI MVP | `60bff50` | `RepoForm`, `WikiViewer`, `Markdown` components; `page.tsx` rewrite; `react-markdown`; 10 UI tests |
| 10 | Real-time SSE status updates | `91d51d0` | `generate.py` real pipeline (repo_loaded→chunked→signals_extracted→done); `stream/route.ts` proxy; `page.tsx` EventSource consumer; 10 backend + 6 frontend new tests |
| 11 | File-level import graph | `544d4c1` | `services/import_graph.py` — Python + JS/TS; 22 tests |
| 12 | Search index over chunks | `0627c74` | `services/search_index.py` — BM25 + substring fallback; 24 tests |
| 13 | LLM client | `f9e7917` | `services/llm.py`, `models/llm_schemas.py` — chat_text, chat_json, fence-strip, retries; 27 tests |
| 14 | Feature proposals | `4645e1b` | `services/propose_features.py` — LLM-driven, banned-word filter, slug normalisation; 31 tests |
| — | Health check button in header | `fc3c067` | `page.tsx` — reusable `api.checkHealth`, button in header; frontend-only |  
| — | Fix SSE stream flush | `2a31a7a` | `generate.py` — emit events one-by-one with `asyncio.sleep(0)` flush; `connecting` event added; 2 test updates |
| 15 | Evidence gathering | `pending` | `services/evidence.py` — seed→import-graph BFS→search hits, dedup, max_chunks/max_chars bounds; 24 tests |

**212 backend tests passing** across: `test_health`, `test_auth`, `test_schemas`, `test_file_filter`, `test_github_client`, `test_repo_loader`, `test_chunker`, `test_signals`, `test_generate_stream`, `test_import_graph`, `test_search_index`, `test_llm`, `test_propose_features`, `test_evidence`.
**25 frontend tests passing**: `route-generate.test.ts` (7) + `route-stream.test.ts` (5) + `ui-basic.test.tsx` (13).

### Next Step

**STEP 16: Backend – Page Writing (LLM) With Chunk Citations**

### Deployment

* **Backend Cloud Run URL:** `https://wiki-generator-backend-ud74aktrjq-uc.a.run.app`
* **GCP project:** `pushstart-481717`, region `us-central1`
* **Latest deployed commit:** `2a31a7a` (SSE flush fix; CI redeploys on push to `backend/**`)
* Smoke checks: `GET /health` → `{"status":"healthy"}` ✅

### Critical Technical Context (for new sessions)

#### Environment & Keys
* Auth env var is **`BACKEND_API_KEY`** — read in `backend/src/config.py`. No hardcoded default; if unset, auth always fails.
* The only valid values are in `.env` at the project root (gitignored, local dev) and GitHub Secrets (Cloud Run). Never hardcode a key value in code or tests.
* `OPENAI_API_KEY` is backend-only; never expose to frontend.
* `GITHUB_TOKEN` — optional; set on Cloud Run via `gcloud run services update` to raise GitHub API rate limits from 60 → 5000 req/hr. `github_client.py` reads it at module load time via `os.environ.get("GITHUB_TOKEN", "")`. For local dev, add it to `.env`.

#### Running Tests
```bash
cd backend
.venv/bin/python -m pytest -q
```
Do NOT use `pytest` directly — always use `.venv/bin/python -m pytest` to avoid PATH issues.
Use `GH_PAGER=cat` prefix for any `gh` CLI commands to avoid pager hangs.

#### Backend Structure
```
backend/src/
├── main.py          # FastAPI app, wires routers; CMD: uvicorn main:app --host 0.0.0.0 --port 8080
├── config.py        # Reads BACKEND_API_KEY, OPENAI_API_KEY (module-level constants)
├── auth.py          # require_api_key() FastAPI dependency
├── models/
│   ├── schemas.py        # GenerateRequest, WikiFeature, GenerateResponse
│   ├── llm_schemas.py    # FeatureProposalList, EvidenceSelection, WikiPageDraft
│   └── repo_snapshot.py  # RepoSnapshot, FileEntry
├── routers/
│   ├── health.py    # GET /health
│   └── generate.py  # POST /api/generate + GET /api/generate/stream (SSE)
└── services/
    ├── github_client.py  # get_repo, get_branch_sha, get_tree, get_file (httpx; GITHUB_TOKEN optional)
    ├── file_filter.py    # should_include(path, size_bytes, is_binary_guess) -> bool
    ├── repo_loader.py    # load_snapshot(owner, repo) -> RepoSnapshot
    ├── chunker.py        # chunk_file(path, content) -> list[Chunk]; semantic + sliding window
    ├── signals.py        # extract_readme_signals, extract_route_signals, extract_entrypoints
    ├── import_graph.py   # build_import_graph(files) -> dict[str, list[str]] — Python + JS/TS
    ├── search_index.py   # SearchIndex.from_chunks(chunks); BM25 + substring fallback
    ├── llm.py            # chat_text(), chat_json(schema) — OpenAI wrapper with retries
    ├── propose_features.py  # propose_features(snapshot, signals) -> FeatureProposalList
    └── evidence.py       # gather_evidence(feature, chunks, graph, index) -> EvidencePack; gather_all_evidence()
```
`PYTHONPATH=/app/src` in Dockerfile; `pythonpath = src` in `pytest.ini`.

#### Frontend Route (Fixed ✅)
`frontend/src/app/api/generate/route.ts` previously passed `repo_url` as a **query param** — now correctly sends a JSON body. Fixed in pre-Step-8 review (`bc154ec`).

#### Backend Test Auth Pattern (Critical)
`config.API_KEY` is a **module-level constant** (`API_KEY = os.environ.get("BACKEND_API_KEY", "")` evaluated at import time).  
`monkeypatch.setenv` does **not** work in backend tests — the value is already cached.  
Always use: `monkeypatch.setattr(config, "API_KEY", "test-key")` in every backend test that touches auth.

#### SSE Architecture (Step 10+)
`GET /api/generate/stream?repo_url=<url>` (FastAPI) streams `text/event-stream` with named events:
`repo_loaded` → `chunked` → `signals_extracted` → `features_proposed` → `pages_written` → `done` (or `error`)  
Each `data:` payload is a JSON object `{ "message": "...", ...stage-specific fields }`.  
Next.js proxy at `frontend/src/app/api/generate/stream/route.ts` forwards `repo_url` param + `x-api-key` header.  
Browser `EventSource` in `page.tsx` parses per-event JSON to present status messages + detail lines.

#### LLM Test Pattern (Critical)
`services/llm.py` holds a module-level `_client`. Use `_set_client(mock)` to inject a mock and always call `_set_client(None)` in teardown to reset. Never call real OpenAI in tests.
```python
from services.llm import _set_client
_set_client(_mock_client("...json..."))
# ... test ...
_set_client(None)
```
Patch `services.llm.time.sleep` to keep retry tests instant.

#### respx Fixtures
Shared respx fixtures use `assert_all_called=False` — this is correct, not a workaround.

#### Deployment Commands
```bash
# Deploy backend
gcloud run deploy wiki-generator-backend --project pushstart-481717 --source ./backend --region us-central1 --allow-unauthenticated

# Check CI
GH_PAGER=cat gh run list --repo gtpooniwala/githubWikiGenerator

# Check logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=wiki-generator-backend" --project pushstart-481717 --limit 20 --format "table(timestamp,textPayload)"
```

### Items Pending ❗

* **Steps 11–19** – Backend pipeline: import graph → search index → LLM client → feature proposals → evidence gathering → page writing → overview page → pipeline orchestrator → wire endpoint
* **Step 20** – Frontend navigable wiki pages (sidebar, `/wiki/[owner]/[repo]` route)
* **Step 21** – CI test gating
* **Step 22** – Final deploy + smoke checks

---

## Tech Stack

| Layer              | Choice                                                   |
| ------------------ | -------------------------------------------------------- |
| Frontend           | Next.js (TypeScript)                                     |
| Backend            | FastAPI (Python)                                         |
| LLM                | OpenAI SDK (`gpt-5-mini` per challenge.md; backend-only key usage) |
| Repo fetch         | GitHub REST API (with optional unauth mode)              |
| Testing (backend)  | pytest + respx + pytest-asyncio                          |
| Testing (frontend) | Vitest + React Testing Library (or Jest if already used) |
| Deployment         | Cloud Run (Docker)                                       |
| CI/CD              | GitHub Actions + WIF                                     |

---

## Target Project Structure (End State)

```
.
├── backend/
│   ├── Dockerfile
│   ├── .dockerignore
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── src/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── models/
│   │   │   ├── schemas.py
│   │   │   └── llm_schemas.py
│   │   ├── routers/
│   │   │   ├── health.py
│   │   │   └── generate.py
│   │   ├── services/
│   │   │   ├── github_client.py
│   │   │   ├── repo_loader.py
│   │   │   ├── file_filter.py
│   │   │   ├── chunker.py
│   │   │   ├── signals.py
│   │   │   ├── import_graph.py
│   │   │   ├── search_index.py
│   │   │   ├── evidence.py
│   │   │   ├── citations.py
│   │   │   ├── llm.py
│   │   │   ├── propose_features.py
│   │   │   ├── write_pages.py
│   │   │   └── pipeline.py
│   │   └── util/
│   │       ├── hashing.py
│   │       └── text.py
│   ├── tests/
│   │   ├── fixtures/
│   │   │   ├── sample_repo_small/
│   │   │   └── github_api/
│   │   ├── test_health.py
│   │   ├── test_auth.py
│   │   ├── test_file_filter.py
│   │   ├── test_chunker.py
│   │   ├── test_import_graph.py
│   │   ├── test_signals.py
│   │   ├── test_search_index.py
│   │   ├── test_evidence.py
│   │   ├── test_citations.py
│   │   └── test_pipeline_smoke.py
│   └── pytest.ini
│
├── frontend/
│   ├── Dockerfile
│   ├── .dockerignore
│   ├── package.json
│   ├── package-lock.json
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx
│   │   │   ├── layout.tsx
│   │   │   ├── api/
│   │   │   │   ├── health/route.ts
│   │   │   │   └── generate/route.ts
│   │   │   └── wiki/
│   │   │       └── [owner]/[repo]/page.tsx
│   │   ├── components/
│   │   │   ├── RepoForm.tsx
│   │   │   ├── WikiViewer.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   └── Markdown.tsx
│   │   └── lib/
│   │       ├── api.ts
│   │       └── types.ts
│   ├── tests/
│   │   ├── route-generate.test.ts
│   │   └── ui-basic.test.tsx
│   └── vitest.config.ts
│
└── .github/workflows/
    ├── test.yml
    ├── deploy-backend.yml
    └── deploy-frontend.yml
```

---

## Canonical API Contract

### Backend

* `GET /health`

  * 200 JSON: `{ "status": "healthy" }`

* `POST /api/generate`

  * Headers: `x-api-key: <BACKEND_API_KEY>`
  * Body:

    ```json
    { "repo_url": "https://github.com/owner/repo" }
    ```
  * Response:

    ```json
    {
      "repo_id": "owner/repo",
      "commit_sha": "<sha>",
      "overview_md": "...",
      "features": [
        {
          "id": "feature-slug",
          "title": "...",
          "description": "...",
          "content_md": "... markdown with citations ..."
        }
      ]
    }
    ```

### Frontend

* `GET /api/health` → proxies to `${BACKEND_URL}/health`
* `POST /api/generate` → proxies to `${BACKEND_URL}/api/generate`.

   - Frontend should forward an app-specific API key in the `x-api-key` header (this is an application-level key used to authenticate frontend→backend requests, not the OpenAI key).
   - The backend must validate the app `x-api-key` and then use `OPENAI_API_KEY` from its environment for LLM calls. Do NOT expose `OPENAI_API_KEY` to the client.

<!-- ## Citations (Verification) Ask user before implementing this. We may change this logic

- All inline citations must be deterministic and point to the analyzed `commit_sha` using GitHub blob URLs with line anchors (for example: `https://github.com/owner/repo/blob/<commit_sha>/path/to/file.py#L10-L20`).
- Add a small verification test that asserts generated markdown contains at least one citation matching the returned `commit_sha`.
- Store the `commit_sha` returned by the repo snapshot step and use it for all citation links so links remain stable and auditable.

--- -->

# Implementation Steps (Atomic, Test-Driven)

> Each step ends with: tests pass → approval → update guide.md -> commit → deploy → smoke checks.

---

## STEP 1: Repo Hygiene + Docker Context Control

### Tasks

1. Ensure root `.gitignore` contains:

   * `node_modules/`, `.next/`, `dist/`, `build/`
   * `.venv/`, `venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`
   * `.env`, `.env.*`, `*.env`
   * `gcp-key.json`

2. Create/verify `frontend/.dockerignore`:

   * `node_modules`
   * `.next`
   * `.git`
   * `.env*`

3. Create/verify `backend/.dockerignore`:

   * `.venv`
   * `__pycache__`
   * `.pytest_cache`
   * `.env*`
   * `.git`

4. Verify `frontend/node_modules` not tracked:

   ```bash
   git ls-files frontend/node_modules | head
   ```

### Acceptance Criteria

* [ ] `git status` shows no accidental artifacts
* [ ] Docker build context does not include `node_modules` or `.venv`

### Validation

* `git status --porcelain`

---

## STEP 2: Backend – Local Venv + Requirements + Pytest Harness

### Tasks

1. Create venv (must be used always for backend work):

   ```bash
   cd backend
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   ```

2. Add `requirements.txt` (runtime) and `requirements-dev.txt` (dev/testing). Make sure to update them as you add dependencies in future steps.

3. Add `pytest.ini` with:

   * `testpaths = tests`
   * `pythonpath = src`

4. Add minimal `src/main.py` FastAPI app (if current differs, refactor) that wires routers.

5. Add minimal tests:

   * `tests/test_health.py` expects `/health` 200

### Acceptance Criteria

* [ ] `pytest -q` passes in venv
* [ ] `uvicorn src.main:app --reload --port 8080` runs locally

### Tests

```bash
cd backend
source .venv/bin/activate
pytest -q
```

---

## STEP 3: Backend – Config + Auth Middleware (BACKEND_API_KEY)

### Tasks

1. Implement `src/config.py`:

   * reads `BACKEND_API_KEY` (app key for frontend→backend auth) and `OPENAI_API_KEY` (kept server-side only)
   * safe defaults for local dev

2. Add auth helper:

   * function `require_api_key(x_api_key: str | None) -> None`
   * raise `HTTPException(401)` on missing/invalid

3. Apply auth to protected routes (at minimum `/api/generate`).

4. Add tests:

   * missing key → 401
   * wrong key → 401
   * correct key → 200 (for stub response)

### Acceptance Criteria

* [ ] Auth enforced only where intended
* [ ] Error response is JSON and stable

### Tests

```bash
pytest -q
```

---

## STEP 4: Backend – Canonical Schemas + Response Contract

### Tasks

1. Create `src/models/schemas.py` with pydantic models:

   * `GenerateRequest(repo_url: HttpUrl)`
   * `WikiFeature(id, title, description, content_md)`
   * `GenerateResponse(repo_id, commit_sha, overview_md, features)`

2. Update router to use models and return stubbed deterministic response.

3. Add contract tests:

   * `POST /api/generate` returns JSON matching schema
   * Validate `repo_id` parsing is correct for GitHub URLs

### Acceptance Criteria

* [ ] Schema is the one used end-to-end (frontend relies on this)

### Tests

```bash
pytest -q
```

---

## STEP 5: Backend – GitHub Repo Snapshot (Tree + Files)

### Goal

Create a reproducible `RepoSnapshot` object:

* metadata (owner/repo, default_branch)
* commit SHA
* file list (path, size, type)
* file contents for selected files

### Tasks

1. Implement `services/github_client.py`:

   * `get_repo(owner, repo)`
   * `get_branch_sha(owner, repo, branch)`
   * `get_tree(owner, repo, sha)` (recursive)
   * `get_file(owner, repo, path, ref_sha)`

2. Implement `services/file_filter.py`:

   * `should_include(path, size_bytes, is_binary_guess) -> bool`
   * rules:

     * exclude directories: `node_modules/`, `.git/`, `dist/`, `build/`, `.next/`, `venv/`, `.venv/`
     * exclude binaries by extension (`.png`, `.jpg`, `.pdf`, `.zip`, `.exe`, etc.)
     * exclude very large files (default 100KB)
     * include: `.md`, `.py`, `.ts`, `.tsx`, `.js`, `.json` (selectively), `.yaml/.yml`, `.toml`, `.graphql`, `.sql`, etc.

3. Implement `services/repo_loader.py`:

   * builds snapshot:

     * selects candidate files via filter
     * downloads contents
     * keeps README if present

4. Add fixtures + tests using `respx` mocking GitHub API responses.

### Intermediate artifacts (write to disk in tests)

* `tests/fixtures/github_api/` JSON responses
* optional: store a small repo snapshot JSON for debugging

### Acceptance Criteria

* [ ] Snapshot contains commit SHA
* [ ] README captured if present
* [ ] Filtering prevents big/binary noise

### Tests

```bash
pytest -q
```

---

## STEP 6: Backend – Chunking (Line-numbered Chunks)

### Goal

Convert each included file into chunks with stable IDs and line ranges.

### Tasks

1. Implement `services/chunker.py`:

   * input: `path`, `content`
   * output: list of chunks:

     * `chunk_id = f"{path}:{start}-{end}"`
     * `start_line`, `end_line`
     * `text`
   * strategies:

     * attempt simple semantic splits for:

       * Python: `def`, `class`
       * JS/TS: `function`, `class`, `export`, `const X = (` patterns
     * fallback sliding window:

       * 60 lines, 10 line overlap

2. Tests:

   * full coverage (no missing lines)
   * stable IDs
   * chunk max lines not exceeded

### Acceptance Criteria

* [ ] Deterministic chunk boundaries
* [ ] IDs usable for citations

### Tests

```bash
pytest -q
```

---

## STEP 7: Backend – Signals Extraction (No LLM)

### Goal

Extract *non-LLM* signals that guide feature discovery:

* README headings
* routes/endpoints
* entry points
* CLI scripts
* config hints

### Tasks

1. Implement `services/signals.py`:

   * `extract_readme_signals(readme_md)`
   * `extract_route_signals(files)` (regex: FastAPI, Express, Next, etc.)
   * `extract_entrypoints(files)` (package.json scripts, main modules)

2. Tests with fixture files.

### Acceptance Criteria

* [ ] Signals are deterministic

---

## STEP 8: Frontend – Proxy `/api/generate` Route

### Tasks

1. Implement `frontend/src/app/api/generate/route.ts`:

   * validates request JSON
   * forwards to `${BACKEND_URL}/api/generate`
   * injects header `x-api-key: BACKEND_API_KEY`
   * forwards response

2. Set up Vitest + React Testing Library.

3. Add route tests:

   * mock `global.fetch`
   * verify header injection
   * missing body → 400
   * backend error propagated correctly

### Acceptance Criteria

* [ ] Route proxies correctly
* [ ] Vitest passes

---

## STEP 9: Frontend – UI MVP (Form + Render)

### Tasks

1. Keep warm-up behavior:

   * on page load: `fetch('/api/health').catch(()=>{})`

2. Build UI:

   * repo URL input
   * generate button
   * loading + error
   * render:

     * overview markdown
     * features list
     * feature markdown

3. Use markdown renderer:

   * `react-markdown` + `remark-gfm`

4. Add minimal UI tests:

   * form submits
   * loading state toggles

### Acceptance Criteria

* [ ] User can generate and read wiki

---

## STEP 10: Frontend – Real-time Status via SSE

### Goal

Show users live progress while the backend pipeline runs.

### Tasks

1. Add a backend SSE stub endpoint `GET /api/generate/stream`:

   * emits progress events: `repo_loaded`, `chunked`, `signals_extracted`, `features_proposed`, `pages_written`, `done`
   * initially returns stubbed events immediately (real streaming wired in Step 19)

2. Frontend: consume SSE stream on the generate page:

   * display status messages as they arrive
   * transition to final result on `done` event

3. Tests:

   * backend: SSE endpoint emits expected events in correct format
   * frontend: status messages render as events are received

### Acceptance Criteria

* [ ] Progress events visible during generation
* [ ] Backend SSE stub passes tests

---
<!-- 
## STEP 11: Frontend – Navigable Wiki Pages

### Tasks

* Add route `/wiki/[owner]/[repo]` for overview
* Add sidebar with feature list
* Add anchor links

### Acceptance Criteria

* [ ] Navigable experience

--- -->

## STEP 11: Backend – File-level Import Graph

### Goal

Create file-to-file dependency graph for evidence expansion.

### Tasks

1. Implement `services/import_graph.py`:

   * parse imports:

     * Python: `import x`, `from x import y`
     * JS/TS: `import ... from`, `require()`
   * resolve relative imports to repo paths
   * ignore external packages

2. Add tests with small fixture repo files.

### Acceptance Criteria

* [ ] Graph edges are correct for fixtures

---

## STEP 12: Backend – Search Index Over Chunks

### Goal

Enable keyword + lightweight semantic retrieval without heavy infra.

### Tasks

1. Implement `services/search_index.py`:

   * store `chunk_id → text`
   * provide search:

     * keyword scoring (BM25-like simple) or TF-IDF
     * fall back to substring matching

2. Tests:

   * searching “login” returns chunks containing login
   * top-k works

### Acceptance Criteria

* [ ] Deterministic results

---

## STEP 13: Backend – LLM Client (Robust JSON)

### Goal

All OpenAI interaction goes through `services/llm.py`.

### Tasks

1. Implement `services/llm.py`:

   * `chat_text(system, user, model="gpt-5-mini", temperature=0.2)` that returns raw text
   * `chat_json(system, user, schema_hint)` that:

     * enforces JSON-only output
     * strips code fences
     * validates via pydantic schema in `models/llm_schemas.py`
   * retries (2) on transient errors

2. Add `models/llm_schemas.py` for LLM outputs:

   * `FeatureProposalList`
   * `EvidenceSelection`
   * `WikiPageDraft`

3. Tests:

   * JSON cleaner handles fenced outputs

### Acceptance Criteria

* [ ] LLM interface returns validated structures

---

## STEP 14: Backend – Feature Proposals (LLM)

### Goal

Generate 5–9 **user-facing** features with entry points.

### Inputs

* repo metadata
* README signals
* route signals
* file list summary

### Tasks

1. Implement `services/propose_features.py` using `llm.chat_json`.

2. Enforce constraints:

   * titles must be user-facing
   * no “utils/helpers/components/frontend/backend”
   * each feature includes:

     * `id` (slug)
     * `title`
     * `description`
     * `seed_paths` (file paths likely relevant)

3. Add tests:

   * schema valid
   * banned words not present

### Acceptance Criteria

* [ ] Reasonable features for fixture repo

---

## STEP 15: Backend – Evidence Gathering (Deterministic + Bounded)

### Goal

For each feature, assemble evidence chunks for page writing.

### Tasks

1. Implement `services/evidence.py`:

   * Start from `seed_paths` → include all chunks from those files
   * Expand via import graph up to `max_hops=2`
   * Add search hits from index using feature keywords
   * Deduplicate chunks
   * Enforce bounds:

     * max chunks per feature (e.g., 40)
     * max total text chars (e.g., 80k)

2. Tests:

   * respects bounds
   * includes seed chunks

### Acceptance Criteria

* [ ] Each feature has evidence pack

---

## STEP 16: Backend – Page Writing (LLM) With Chunk Citations

### Goal

Generate markdown per feature with citations.

### Citation format (internal)

LLM must cite as:

* `[path:start-end]` matching chunk IDs

### Tasks

1. Implement `services/write_pages.py`:

   * prompt includes:

     * feature title + description
     * evidence chunks (with IDs)
     * instruction: cite every nontrivial claim
     * output markdown only

2. Implement `services/citations.py`:

   * convert `[path:start-end]` → markdown link to GitHub permalink:

     * `https://github.com/{owner}/{repo}/blob/{sha}/{path}#L{start}-L{end}`

3. Tests:

   * citations convert correctly
   * invalid citations are either removed or flagged

### Acceptance Criteria

* [ ] Markdown contains citations
* [ ] Links resolve to GitHub blob URLs

---

## STEP 17: Backend – Overview Page (LLM)

### Goal

Generate a repo-level overview with citations:

* what it does
* architecture at a high level
* how to run

### Tasks

* Implement `services/wiki_writer.py` or a function in `write_pages.py`
* Use a smaller evidence set:

  * README
  * package.json/pyproject
  * main entrypoints

### Acceptance Criteria

* [ ] overview_md returned

---

## STEP 18: Backend – Pipeline Orchestrator

### Goal

One function that runs the full pipeline with stable intermediate artifacts.

### Tasks

1. Implement `services/pipeline.py`:

   * `run_pipeline(repo_url: str) -> GenerateResponse`

2. Persist intermediate artifacts **optionally** (debug mode):

   * snapshot summary JSON
   * chunk index stats
   * proposed features JSON
   * evidence packs stats

3. Add a smoke test (no real OpenAI call) that stubs LLM:

   * patch `llm.chat_json` and `llm.chat_text`
   * assert pipeline returns GenerateResponse

### Acceptance Criteria

* [ ] Pipeline runs deterministically with mocked LLM

---

## STEP 19: Backend – `/api/generate` Endpoint

### Tasks

* Implement router `routers/generate.py`:

  * parse input
  * auth
  * call pipeline
  * return response

### Tests

* contract tests
* auth tests

### Acceptance Criteria

* [ ] Endpoint works locally

---

<!-- ## STEP 17: Frontend – Proxy `/api/generate` Route

### Tasks

1. Implement `frontend/src/app/api/generate/route.ts`:

   * validates request JSON
   * forwards to `${BACKEND_URL}/api/generate`
   * injects header `x-api-key: BACKEND_API_KEY`
   * forwards response

2. Add route tests:

   * mock `global.fetch`
   * verify header injection

### Acceptance Criteria

* [ ] Route proxies correctly

---

## STEP 18: Frontend – UI MVP (Form + Render)

### Tasks

1. Keep warm-up behavior:

   * on page load: `fetch('/api/health').catch(()=>{})`

2. Build UI:

   * repo URL input
   * generate button
   * loading + error
   * render:

     * overview markdown
     * features list
     * feature markdown

3. Use markdown renderer:

   * `react-markdown` + `remark-gfm`

4. Add minimal UI tests:

   * form submits
   * loading state toggles

### Acceptance Criteria

* [ ] User can generate and read wiki

--- -->

## STEP 20: Frontend – Navigable Wiki Pages

### Tasks

* Add route `/wiki/[owner]/[repo]` for overview
* Add sidebar with feature list
* Add anchor links

### Acceptance Criteria

* [ ] Navigable experience

---

## STEP 21: CI – Tests Gate Deploy

### Tasks

1. Add/confirm `.github/workflows/test.yml`:

   * Backend:

     * create venv
     * install requirements
     * `pytest -q`
   * Frontend:

     * `npm ci`
     * `npm run test`
     * `npm run build`

2. Ensure deploy workflows either:

   * depend on test workflow, or
   * run tests inline before deploy

### Acceptance Criteria

* [ ] broken tests prevent deploy

---

## STEP 22: Deploy + Smoke Checks (Every Merge)

### Required env vars

Backend Cloud Run:

* `BACKEND_API_KEY`
* `OPENAI_API_KEY`

Frontend Cloud Run:

* `BACKEND_URL`
* `BACKEND_API_KEY`

### Smoke checks

* Backend:

  * `GET /health`
* Frontend:

  * `GET /api/health`
  * `POST /api/generate` with sample repo

---

# Appendices

## Appendix A: LLM Prompts (Templates)

### A1: Feature proposal prompt

**System**

* You are a senior engineer writing user-facing documentation.
* Output JSON only.

**User** (template)

* Repo: {repo_id}
* README snippets:

  * {readme_headings}
* Routes/endpoints signals:

  * {routes}
* Entry points:

  * {entrypoints}
* Instructions:

  * Propose 5–9 user-facing features.
  * Avoid technical layers (no “utils”, “helpers”, “components”, “frontend”, “backend”).
  * Each feature must include seed file paths.

Output JSON schema: `FeatureProposalList`.

### A2: Page writing prompt

**System**

* You produce accurate markdown documentation. Cite sources.

**User**

* Feature: {title}
* Description: {description}
* Evidence chunks (each with ID):

  * {chunk_id}: {chunk_text}

Instructions:

* Write markdown for this feature.
* Every nontrivial claim must include at least one citation in the form `[path:start-end]`.
* Do not invent file paths.
* Output markdown only.

---

## Appendix B: Determinism + Limits

Recommended defaults:

* max files downloaded: 300
* max file size: 100KB
* max chunks per feature: 40
* max hops in import graph expansion: 2
* LLM retries: 2

---

## Appendix C: Cloud Run Notes

* Cold starts are normal.
* Frontend warm-up call to `/api/health` is recommended.
* Deploy time for frontend from source can be 3–7 minutes.
