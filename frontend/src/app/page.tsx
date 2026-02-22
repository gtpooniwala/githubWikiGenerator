'use client';

import { useCallback, useEffect, useState } from 'react';
import { checkHealth as apiCheckHealth, generateWiki, GenerateResponse } from '@/lib/api';
import { RepoForm } from '@/components/RepoForm';
import { WikiViewer } from '@/components/WikiViewer';

const SSE_EVENTS = ['repo_loaded', 'chunked', 'signals_extracted', 'features_proposed', 'pages_written', 'done'] as const;

interface StatusMessage {
  label: string;
  detail?: string;
}

function parseStatusDetail(event: string, data: Record<string, unknown>): string | undefined {
  if (event === 'repo_loaded' && data.file_count != null) return `${data.file_count} files · commit ${String(data.commit_sha ?? '').slice(0, 7)}`;
  if (event === 'chunked' && data.chunk_count != null) return `${data.chunk_count} chunks`;
  if (event === 'signals_extracted') {
    const parts = [];
    if (data.routes) parts.push(`${data.routes} routes`);
    if (data.headings) parts.push(`${data.headings} headings`);
    if (data.entrypoints) parts.push(`${data.entrypoints} entrypoints`);
    return parts.length ? parts.join(' · ') : undefined;
  }
  return undefined;
}

type HealthStatus = 'idle' | 'checking' | 'healthy' | 'unhealthy';

export default function Home() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [wikiData, setWikiData] = useState<GenerateResponse | null>(null);
  const [statusMessages, setStatusMessages] = useState<StatusMessage[]>([]);
  const [healthStatus, setHealthStatus] = useState<HealthStatus>('idle');

  const checkHealth = useCallback(async () => {
    setHealthStatus('checking');
    try {
      const data = await apiCheckHealth();
      setHealthStatus(data?.status === 'healthy' ? 'healthy' : 'unhealthy');
    } catch {
      setHealthStatus('unhealthy');
    }
  }, []);

  // Auto-check health on mount (also warms up Cloud Run cold-start)
  useEffect(() => {
    checkHealth();
  }, [checkHealth]);

  const handleGenerate = useCallback(async (repoUrl: string) => {
    setLoading(true);
    setError(null);
    setWikiData(null);
    setStatusMessages([]);

    // Open SSE stream for live progress updates
    const es = new EventSource(`/api/generate/stream?repo_url=${encodeURIComponent(repoUrl)}`);
    SSE_EVENTS.forEach((eventName) => {
      es.addEventListener(eventName, (e: MessageEvent) => {
        let parsed: Record<string, unknown> = {};
        try { parsed = JSON.parse(e.data); } catch { /* ignore */ }
        setStatusMessages((prev) => [
          ...prev,
          { label: String(parsed.message ?? eventName), detail: parseStatusDetail(eventName, parsed) },
        ]);
      });
    });
    es.onerror = () => es.close();

    try {
      const data = await generateWiki(repoUrl);
      setWikiData(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong. Please try again.');
    } finally {
      es.close();
      setLoading(false);
    }
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
      {/* Header */}
      <header className="border-b border-slate-200 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-4 flex items-center gap-3">
          <span className="text-2xl" aria-hidden="true">📚</span>
          <div>
            <h1 className="text-lg font-bold text-slate-900 leading-none">Wiki Generator</h1>
            <p className="text-xs text-slate-500 mt-0.5">Instant docs for any public GitHub repo</p>
          </div>

          {/* Health check — pushed to top-right */}
          <div className="ml-auto flex items-center gap-2">
            {/* Status indicator */}
            {healthStatus !== 'idle' && (
              <span
                aria-label={`Backend status: ${healthStatus}`}
                className={`flex items-center gap-1.5 text-xs font-medium px-2 py-1 rounded-full border ${
                  healthStatus === 'checking'
                    ? 'bg-slate-50 border-slate-200 text-slate-400'
                    : healthStatus === 'healthy'
                    ? 'bg-green-50 border-green-200 text-green-700'
                    : 'bg-red-50 border-red-200 text-red-600'
                }`}
              >
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    healthStatus === 'checking'
                      ? 'bg-slate-300 animate-pulse'
                      : healthStatus === 'healthy'
                      ? 'bg-green-500'
                      : 'bg-red-500'
                  }`}
                />
                {healthStatus === 'checking' ? 'Checking…' : healthStatus === 'healthy' ? 'Backend healthy' : 'Backend unreachable'}
              </span>
            )}

            <button
              onClick={checkHealth}
              disabled={healthStatus === 'checking'}
              aria-label="Check backend health"
              className="text-xs font-medium px-3 py-1.5 rounded-md border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 hover:border-slate-300 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {healthStatus === 'checking' ? 'Checking…' : 'Check health'}
            </button>
          </div>
        </div>
      </header>

      {/* Hero + Form */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 py-12">
        <div className="text-center mb-8">
          <h2 className="text-3xl sm:text-4xl font-bold text-slate-900 mb-3">
            Generate developer docs in one click
          </h2>
          <p className="text-slate-500 text-lg max-w-xl mx-auto">
            Paste a public GitHub repository URL and get a navigable wiki organized by user-facing features.
          </p>
        </div>

        <div className="max-w-2xl mx-auto">
          <RepoForm onSubmit={handleGenerate} loading={loading} />
        </div>

        {/* Error state */}
        {error && (
          <div
            role="alert"
            className="mt-6 max-w-2xl mx-auto p-4 bg-red-50 border border-red-200 rounded-lg flex gap-3 text-sm text-red-700"
          >
            <span className="shrink-0">❌</span>
            <span>{error}</span>
          </div>
        )}

        {/* Loading state */}
        {loading && (
          <div
            role="status"
            aria-label="Generating wiki"
            className="mt-10 flex flex-col items-center gap-4 text-slate-500"
          >
            <svg className="animate-spin h-8 w-8 text-blue-500" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            {statusMessages.length > 0 ? (
              <ul className="space-y-1 text-center">
                {statusMessages.map((msg, i) => (
                  <li
                    key={i}
                    className={`text-sm ${i === statusMessages.length - 1 ? 'text-blue-600 font-medium' : 'text-slate-400'}`}
                  >
                    {i === statusMessages.length - 1 ? '▶ ' : '✓ '}
                    {msg.label}
                    {msg.detail && <span className="ml-1 opacity-70">({msg.detail})</span>}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm">Analyzing repository and generating wiki…</p>
            )}
          </div>
        )}
      </section>

      {/* Wiki output */}
      {wikiData && !loading && (
        <section className="max-w-5xl mx-auto px-4 sm:px-6 pb-16">
          <WikiViewer data={wikiData} />
        </section>
      )}
    </div>
  );
}
