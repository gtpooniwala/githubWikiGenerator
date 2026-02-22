import { NextRequest } from 'next/server';

// Allow this route to run for up to 15 minutes on Vercel/Next.js.
// Cloud Run timeout is set to 900 s separately via gcloud.
export const maxDuration = 900;

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8080';
const BACKEND_API_KEY = process.env.BACKEND_API_KEY || '';

// Leave 20 s headroom so we can return a clean error before Cloud Run kills us.
const PROXY_TIMEOUT_MS = 880_000;

export async function GET(request: NextRequest) {
  const repoUrl = request.nextUrl.searchParams.get('repo_url');
  if (!repoUrl) {
    return new Response(JSON.stringify({ detail: 'repo_url query param is required' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const backendUrl = new URL(`${BACKEND_URL}/api/generate/stream`);
  backendUrl.searchParams.set('repo_url', repoUrl);

  try {
    const response = await fetch(backendUrl.toString(), {
      headers: {
        'x-api-key': BACKEND_API_KEY,
        Accept: 'text/event-stream',
      },
      signal: AbortSignal.timeout(PROXY_TIMEOUT_MS),
    });

    if (!response.ok) {
      return new Response(null, { status: response.status });
    }

    return new Response(response.body, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
      },
    });
  } catch (err) {
    const isTimeout = err instanceof Error && err.name === 'TimeoutError';
    return new Response(null, { status: isTimeout ? 504 : 503 });
  }
}
