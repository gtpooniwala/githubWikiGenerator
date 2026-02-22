// @vitest-environment node
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { NextRequest } from 'next/server';
import { POST } from '../src/app/api/generate/route';

function makeRequest(body: unknown): NextRequest {
  return new NextRequest('http://localhost/api/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

describe('POST /api/generate route', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.unstubAllGlobals();
  });

  it('returns 400 when repo_url is missing', async () => {
    const req = makeRequest({});
    const res = await POST(req);
    expect(res.status).toBe(400);
    const data = await res.json();
    expect(data.detail).toBe('repo_url is required');
  });

  it('returns 400 when body is empty object', async () => {
    const req = makeRequest({ other_field: 'value' });
    const res = await POST(req);
    expect(res.status).toBe(400);
  });

  it('injects x-api-key header when forwarding to backend', async () => {
    const mockFetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          repo_id: 'owner/repo',
          commit_sha: 'abc123',
          overview_md: '# Overview',
          features: [],
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      )
    );
    vi.stubGlobal('fetch', mockFetch);

    const req = makeRequest({ repo_url: 'https://github.com/owner/repo' });
    const res = await POST(req);

    expect(res.status).toBe(200);
    expect(mockFetch).toHaveBeenCalledOnce();

    const [url, callOptions] = mockFetch.mock.calls[0] as [string, RequestInit & { headers: Record<string, string> }];
    expect(url).toContain('/api/generate');
    expect(callOptions.headers['x-api-key']).toBeDefined();
    expect(callOptions.headers['Content-Type']).toBe('application/json');
  });

  it('forwards request body to backend', async () => {
    const mockFetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ repo_id: 'owner/repo', commit_sha: 'abc', overview_md: '', features: [] }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      )
    );
    vi.stubGlobal('fetch', mockFetch);

    const req = makeRequest({ repo_url: 'https://github.com/owner/repo' });
    await POST(req);

    const [, callOptions] = mockFetch.mock.calls[0] as [string, RequestInit];
    const sentBody = JSON.parse(callOptions.body as string);
    expect(sentBody.repo_url).toBe('https://github.com/owner/repo');
  });

  it('propagates backend 422 error status and body', async () => {
    const mockFetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ detail: 'Invalid GitHub URL' }),
        { status: 422, headers: { 'Content-Type': 'application/json' } }
      )
    );
    vi.stubGlobal('fetch', mockFetch);

    const req = makeRequest({ repo_url: 'https://github.com/owner/repo' });
    const res = await POST(req);

    expect(res.status).toBe(422);
    const data = await res.json();
    expect(data.detail).toBe('Invalid GitHub URL');
  });

  it('propagates backend 401 error status', async () => {
    const mockFetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ detail: 'Unauthorized' }),
        { status: 401, headers: { 'Content-Type': 'application/json' } }
      )
    );
    vi.stubGlobal('fetch', mockFetch);

    const req = makeRequest({ repo_url: 'https://github.com/owner/repo' });
    const res = await POST(req);

    expect(res.status).toBe(401);
  });

  it('returns 503 when backend is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('ECONNREFUSED')));

    const req = makeRequest({ repo_url: 'https://github.com/owner/repo' });
    const res = await POST(req);

    expect(res.status).toBe(503);
    const data = await res.json();
    expect(data.detail).toBe('Backend request failed');
  });
});
