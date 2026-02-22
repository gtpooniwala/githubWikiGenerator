'use client';

import { use, useEffect, useState } from 'react';
import Link from 'next/link';
import { GenerateResponse } from '@/lib/api';
import { WikiViewer } from '@/components/WikiViewer';

interface WikiPageProps {
  params: Promise<{ owner: string; repo: string }>;
}

interface StatusMessage {
  label: string;
  detail?: string;
}

const SSE_EVENTS = [
  'connecting',
  'repo_loaded',
  'signals_extracted',
  'chunked',
  'import_graph_built',
  'search_index_built',
  'features_proposed',
  'evidence_gathered',
  'pages_written',
  'overview_written',
  'done',
] as const;

function parseStatusDetail(event: string, data: Record<string, unknown>): string | undefined {
  if (event === 'repo_loaded' && data.file_count != null)
    return `${data.file_count} files · commit ${String(data.commit_sha ?? '').slice(0, 7)}`;
  if (event === 'chunked' && data.chunk_count != null) return `${data.chunk_count} chunks`;
  if (event === 'signals_extracted') {
    const parts: string[] = [];
    if (data.routes) parts.push(`${data.routes} routes`);
    if (data.headings) parts.push(`${data.headings} headings`);
    if (data.entrypoints) parts.push(`${data.entrypoints} entrypoints`);
    return parts.length ? parts.join(' · ') : undefined;
  }
  if (event === 'import_graph_built' && data.edges != null) return `${data.edges} edges`;
  if (event === 'search_index_built' && data.indexed_chunks != null)
    return `${data.indexed_chunks} chunks indexed`;
  if (event === 'features_proposed' && Array.isArray(data.features))
    return (data.features as Array<{ title: string }>).map((f) => f.title).join(', ');
  if (event === 'evidence_gathered' && data.feature_count != null)
    return `${data.feature_count} features`;
  return undefined;
}

export default function WikiPage({ params }: WikiPageProps) {
  const { owner, repo } = use(params);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [wikiData, setWikiData] = useState<GenerateResponse | null>(null);
  const [statusMessages, setStatusMessages] = useState<StatusMessage[]>([]);

  useEffect(() => {
    const repoUrl = `https://github.com/${owner}/${repo}`;
    setLoading(true);
    setError(null);
    setStatusMessages([]);
    setWikiData(null);

    const es = new EventSource(`/api/generate/stream?repo_url=${encodeURIComponent(repoUrl)}`);

    SSE_EVENTS.forEach((eventName) => {
      es.addEventListener(eventName, (e: MessageEvent) => {
        let parsed: Record<string, unknown> = {};
        try { parsed = JSON.parse(e.data); } catch { /* ignore */ }
        setStatusMessages((prev) => [
          ...prev,
          { label: String(parsed.message ?? eventName), detail: parseStatusDetail(eventName, parsed) },
        ]);
        if (eventName === 'done') {
          es.close();
          setWikiData(parsed as unknown as GenerateResponse);
          setLoading(false);
        }
      });
    });

    es.addEventListener('error', (e: MessageEvent) => {
      // Named server-sent "error" event: e.data is the JSON payload.
      // Connection-level errors also fire this listener but have no e.data.
      let msg = 'Connection to server lost. The request may have timed out — please try again.';
      try { msg = JSON.parse(e.data)?.message ?? msg; } catch { /* ignore — e.data absent on connection errors */ }
      setError(msg);
      es.close();
      setLoading(false);
    });

    es.onerror = () => {
      // Fallback: ensure the page never stays blank if the named-event listener
      // didn't fire (e.g. stream closed before the first event was received).
      setError((prev) => prev ?? 'Connection to server lost. The request may have timed out — please try again.');
      setLoading(false);
    };

    return () => es.close();
  }, [owner, repo]);

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
      {/* Header */}
      <header className="border-b border-slate-200 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 flex items-center gap-3">
          <Link
            href="/"
            className="text-slate-500 hover:text-slate-700 transition-colors text-sm flex items-center gap-1.5"
            aria-label="Back to home"
          >
            ← Back
          </Link>
          <span className="text-slate-300">|</span>
          <span className="text-2xl" aria-hidden="true">📚</span>
          <div className="min-w-0">
            <h1 className="text-lg font-bold text-slate-900 leading-none truncate">Wiki Generator</h1>
            <p className="text-xs text-slate-500 mt-0.5 truncate">
              {owner}/{repo}
            </p>
          </div>
          <a
            href={`https://github.com/${owner}/${repo}`}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto text-xs font-medium px-3 py-1.5 rounded-md border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 hover:border-slate-300 transition-colors"
          >
            View on GitHub ↗
          </a>
        </div>
      </header>

      {/* Loading state */}
      {loading && (
        <div
          role="status"
          aria-label="Generating wiki"
          className="flex flex-col items-center justify-center gap-6 py-32 text-slate-500"
        >
          <svg className="animate-spin h-10 w-10 text-blue-500" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          <div className="text-center">
            <p className="font-medium text-slate-700">Generating wiki for {owner}/{repo}</p>
            {statusMessages.length === 0 && (
              <p className="text-sm text-slate-400 mt-1">This may take up to a minute…</p>
            )}
          </div>
          {statusMessages.length > 0 && (
            <ul className="mt-2 space-y-1 text-sm">
              {statusMessages.map((msg, i) => {
                const isLast = i === statusMessages.length - 1;
                return (
                  <li
                    key={i}
                    className={`flex items-baseline gap-2 ${
                      isLast ? 'text-blue-600 font-medium' : 'text-slate-500'
                    }`}
                  >
                    <span className="shrink-0 w-4 text-center">{isLast ? '▶' : '✓'}</span>
                    <span>
                      {msg.label}
                      {msg.detail && <span className="ml-1 text-slate-400">({msg.detail})</span>}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}

      {/* Error state */}
      {!loading && error && (
        <div className="max-w-2xl mx-auto px-4 sm:px-6 py-16">
          <div
            role="alert"
            className="p-6 bg-red-50 border border-red-200 rounded-xl text-red-700"
          >
            <p className="font-semibold mb-1">Failed to generate wiki</p>
            <p className="text-sm">{error}</p>
            <Link
              href="/"
              className="mt-4 inline-block text-sm font-medium text-red-700 underline"
            >
              Try again from home
            </Link>
          </div>
        </div>
      )}

      {/* Wiki content */}
      {!loading && wikiData && (
        <main className="max-w-6xl mx-auto px-4 sm:px-6 py-8 pb-16">
          <WikiViewer data={wikiData} />
        </main>
      )}
    </div>
  );
}
