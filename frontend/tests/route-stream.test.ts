// @vitest-environment node
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { NextRequest } from 'next/server';
import { GET } from '../src/app/api/generate/stream/route';

function makeRequest(repoUrl?: string): NextRequest {
  const url = repoUrl
    ? `http://localhost/api/generate/stream?repo_url=${encodeURIComponent(repoUrl)}`
    : 'http://localhost/api/generate/stream';
  return new NextRequest(url);
}

describe('GET /api/generate/stream route', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.unstubAllGlobals();
  });

  it('returns 400 when repo_url query param is missing', async () => {
    const res = await GET(makeRequest());
    expect(res.status).toBe(400);
    const data = await res.json();
    expect(data.detail).toMatch(/repo_url/i);
  });

  it('proxies to backend with repo_url and x-api-key header', async () => {
    const mockFetch = vi.fn().mockResolvedValue(
      new Response('event: done\ndata: {"message":"Complete"}\n\n', {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
      })
    );
    vi.stubGlobal('fetch', mockFetch);

    const res = await GET(makeRequest('https://github.com/owner/repo'));

    expect(res.status).toBe(200);
    expect(mockFetch).toHaveBeenCalledOnce();

    const [url, opts] = mockFetch.mock.calls[0] as [string, RequestInit & { headers: Record<string, string> }];
    expect(url).toContain('/api/generate/stream');
    expect(url).toContain('repo_url=');
    expect(opts.headers['x-api-key']).toBeDefined();
    expect(opts.headers['Accept']).toBe('text/event-stream');
  });

  it('returns text/event-stream content type on success', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response('event: done\ndata: {}\n\n', {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
      })
    ));

    const res = await GET(makeRequest('https://github.com/owner/repo'));
    expect(res.headers.get('Content-Type')).toBe('text/event-stream');
  });

  it('propagates non-200 backend status', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 401 })));

    const res = await GET(makeRequest('https://github.com/owner/repo'));
    expect(res.status).toBe(401);
  });

  it('returns 503 when backend is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('ECONNREFUSED')));

    const res = await GET(makeRequest('https://github.com/owner/repo'));
    expect(res.status).toBe(503);
  });
});

