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

The backend runs a multi-stage pipeline when a repo URL is submitted:

1. **Snapshot** — fetches the repo tree and downloads included source files via GitHub REST API
2. **Filter** — excludes binaries, build artefacts, and oversized files
3. **Chunk** — splits each file into semantically bounded chunks with stable `path:start-end` IDs
4. **Signals** — extracts README headings, API routes, and entry points without LLM calls
5. **Import graph** — builds a file-to-file dependency graph (Python + JS/TS) for evidence expansion
6. **Search index** — BM25 keyword index over all chunks for feature-scoped retrieval
7. **Feature proposals** — LLM identifies 5–9 user-facing features with seed file paths
8. **Evidence gathering** — assembles bounded evidence packs per feature via seed files + import graph expansion + search hits
9. **Page writing** — LLM generates markdown per feature with inline chunk citations converted to GitHub permalink URLs
10. **Overview** — repo-level summary generated from README + entry points

Progress events are streamed to the browser via SSE (`GET /api/generate/stream`) so users see live status updates while the pipeline runs.

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
