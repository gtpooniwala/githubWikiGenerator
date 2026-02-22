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
