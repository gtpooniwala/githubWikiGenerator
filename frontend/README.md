# Wiki Generator – Frontend

Next.js (App Router, TypeScript) frontend for the GitHub Wiki Generator.

## Local Dev

```bash
npm install
npm run dev    # http://localhost:3000
```

Create `frontend/.env.local`:
```
BACKEND_URL=http://localhost:8080
BACKEND_API_KEY=<same key as backend BACKEND_API_KEY>
```

## Routes

| Route | Purpose |
|-------|---------|
| `GET /api/health` | Proxies to `${BACKEND_URL}/health` |
| `POST /api/generate` | Proxies to `${BACKEND_URL}/api/generate`, injects `x-api-key` header |

## Tests

```bash
npm run test
```

## Notes

- `BACKEND_API_KEY` is injected server-side into proxied requests — never exposed to the browser.
- On page load, a warm-up `fetch('/api/health')` fires silently to prevent cold-start latency.
