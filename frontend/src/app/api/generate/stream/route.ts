import { NextRequest } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8080';
const API_KEY = process.env.BACKEND_API_KEY || '';

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
        'x-api-key': API_KEY,
        Accept: 'text/event-stream',
      },
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
  } catch {
    return new Response(null, { status: 503 });
  }
}
