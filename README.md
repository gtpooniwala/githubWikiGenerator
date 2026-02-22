# GitHub Wiki Generator

Automatic wiki generator for public GitHub repositories. Analyses repo code and produces user-facing feature documentation with inline source citations.

## Architecture

| Layer | Tech | Deployed |
|-------|------|---------|
| Frontend | Next.js (App Router, TypeScript) | Cloud Run |
| Backend | FastAPI (Python 3.12) | Cloud Run |
| LLM | OpenAI (`gpt-4o-mini`) | backend-only |
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

## Implementation Progress

| Step | Status | Description |
|------|--------|-------------|
| 1 | ✅ | Repo hygiene + Docker context control |
| 2 | ✅ | Backend venv + requirements + pytest harness |
| 3 | ✅ | Config + auth middleware (BACKEND_API_KEY) |
| 4 | ✅ | Canonical Pydantic schemas |
| 5 | ✅ | GitHub repo snapshot (tree + files) |
| 6 | ✅ | Chunker (semantic + sliding window) |
| 7 | ✅ | Signals extraction (README, routes, entrypoints) |
| 8–21 | 🔲 | Import graph → search index → LLM pipeline → frontend UI |

See [guide.md](guide.md) for full execution spec and current status.

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
