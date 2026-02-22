# GitHub Wiki Generator

Automatic wiki generator for public GitHub repositories. Analyses repo code and produces user-facing feature documentation with inline source citations.

---

## Usage — Try the Live Demo

The app is fully deployed and ready to use. No setup required.

**[Open the frontend](https://wiki-generator-frontend-254204084242.us-central1.run.app/)**

1. The page may take **a few seconds to load** on first visit while the frontend and backend warm up. A health-check runs automatically — wait for it to show a green "healthy" status before proceeding.
2. Paste any **public GitHub repository URL** into the input box, or select one of the pre-filled examples.
3. Click **Generate Wiki**.
4. Watch live progress as the pipeline runs. Wiki generation typically completes in **under 5 minutes**.
5. Once the wiki appears, use the **Ask the wiki** panel at the bottom of the content area to ask questions about the repository — the entire generated wiki is used as context for each answer.

The output includes an **Overview page** (what the project does, architecture, quickstart) and a set of **Feature pages** — one per user-facing feature, each with inline citations that link to the exact source lines on GitHub at the analysed commit SHA.

> **Note on architecture:** The backend is separate from the frontend and requires an API key to call directly. 

**Having trouble?**

- If the page or health-check takes **longer than ~1 minute** to respond, or if you see an error, please reach out to me directly.
- If wiki generation takes **longer than 10 minutes**, something has gone wrong — contact me and I'll look into it.

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

## Live URLs

| Service | URL |
|---------|-----|
| Backend | `https://wiki-generator-backend-ud74aktrjq-uc.a.run.app` |
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

**Required env vars** — defined in `.env` at the project root:

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

### `POST /api/qa`
Headers: `x-api-key: <BACKEND_API_KEY>`

Request:
```json
{
  "repo_id": "owner/repo",
  "question": "How does authentication work?",
  "overview_md": "...",
  "features": [{ "id": "...", "title": "...", "description": "...", "content_md": "..." }]
}
```

Response:
```json
{ "answer": "..." }
```

The full wiki (overview + all feature pages) is passed as context in a single LLM call. No retrieval step is needed — the complete wiki fits well within `gpt-5-mini`'s 400,000 token context window.

## How It Works

The backend runs a deterministic multi-stage pipeline when a repo URL is submitted. Every stage feeds the next; no stage makes LLM calls unless noted.

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
| 8 | Propose features | `propose_features.py` | ✓ `gpt-5-mini` |
| 9 | Gather evidence | `evidence.py` (seed → graph expand → BM25 → dedup) | — |
| 10 | Write feature pages | `write_pages.py` → `citations.py` (chunk ID → permalink) | ✓ `gpt-5-mini` × N |
| 11 | Write overview | `write_pages.py` | ✓ `gpt-5-mini` |
| 12 | Assemble response | `pipeline.py` | — |

### SSE streaming

All ten pipeline stages run inside the SSE generator (`GET /api/generate/stream`). The browser receives a named event as each stage completes:

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

See [guide.md](guide.md) for the full execution spec.
For architectural tradeoffs and planned retrieval/chunking upgrades, see [pipeline-improvements.md](pipeline-improvements.md).


## Challenge Notes

This project was built for the **cubic Coding Challenge** — a 48-hour sprint to build an automatic wiki generator for public GitHub repos.

Detailed rationale and alternatives for pipeline quality improvements are documented in [pipeline-improvements.md](pipeline-improvements.md).

### What I’d improve with more time

- **Chunking and graph creation strategy** — current chunking is mostly line-window based with regex semantic hints, and graph expansion is file-level + outgoing imports only. This can introduce noisy evidence and miss caller-side context. Planned upgrades (AST/tree-sitter chunking, reverse edges, and symbol-aware traversal) are described in [pipeline-improvements.md](pipeline-improvements.md).
- **Parallel feature page writing** — feature pages are written sequentially (one LLM call completes before the next starts). All evidence packs are independent so this is trivially parallelisable with a thread pool, cutting total LLM wall-clock time from ~N×4s to ~4s regardless of feature count.
- **Seed path and citation validation** — the LLM can hallucinate `seed_paths` that don't exist in the snapshot, silently producing thin evidence packs. Separately, the citation resolver converts any `[path:N-M]` pattern to a GitHub URL without checking the path was actually analyzed; hallucinated paths become valid-looking links that 404. Both are fixable with a membership check against the known file list and chunk ID set.
- **Richer feature proposal context** — the LLM currently sees only file paths, README headings, and HTTP routes when proposing features. Adding the top-level symbol names per file (function/class names already identified by the chunker's semantic boundary pass) would give it real code signal at near-zero token cost and improve seed path accuracy for repos with sparse READMEs.
- **Caching** — cache downloaded files and embeddings keyed by `(owner, repo, commit_sha)` so repeat requests on the same commit are instant.
- **Database**- Save previously generated wikis and chat history in a simple database (eg. SQLite) keyed by `repo_id + commit_sha`. This would allow instant retrieval of prior wikis without re-running the pipeline. A "Regenerate wiki" button could trigger a fresh generation while keeping the old wiki available for comparison.
- **Q&A chat history** — the "Ask the wiki" sidebar panel currently has no persistent conversation history; each question is answered in isolation with no memory of prior turns. Implementing a React context (or Zustand store) to retain `qaPairs` at the app level, combined with a multi-turn prompt that includes prior exchanges, would let users build on previous answers and reference earlier responses. Session storage could persist the history across page navigations without any backend changes.

### Bonus features implemented

- **Q&A across the wiki** — an "Ask the wiki" panel lives at the bottom of every wiki page. The full generated wiki (overview + all feature pages, typically 3–8k tokens) is passed as context to a single `gpt-5-mini` call, giving the model cross-page awareness. No retrieval step is needed at this scale.

### What isn’t production-ready

- **Scaling testing** — the system is only tested against a handful of small-to-medium repos. It should work in theory on any public GitHub repo, but without testing against a wider variety of codebases, languages and styles there may be edge cases that break the pipeline or produce poor output.
- **No rate limiting** on the `/api/generate` endpoint — a single request triggers 10+ LLM calls and GitHub API fetches; without throttling this is DoS-able.
- **No request queuing** — concurrent generate requests will compete for OpenAI quota and GitHub rate limits.
- **Single Cloud Run instance** — the backend is stateless but cold-start latency (2–4 s) would need a min-instances setting for production traffic.
- **Citation hallucination** — the LLM can cite plausible-but-wrong line ranges; a post-generation step that checks cited ranges against the actual analyzed chunks (stripping or flagging those that don't match) would improve trust without requiring a second LLM call.
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
