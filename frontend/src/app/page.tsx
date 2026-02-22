'use client';

import { useCallback, useEffect, useState } from 'react';
import { generateWiki, GenerateResponse } from '@/lib/api';
import { RepoForm } from '@/components/RepoForm';
import { WikiViewer } from '@/components/WikiViewer';

export default function Home() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [wikiData, setWikiData] = useState<GenerateResponse | null>(null);

  // Warm-up: silent health check on mount so Cloud Run cold-start resolves early
  useEffect(() => {
    fetch('/api/health').catch(() => {});
  }, []);

  const handleGenerate = useCallback(async (repoUrl: string) => {
    setLoading(true);
    setError(null);
    setWikiData(null);
    try {
      const data = await generateWiki(repoUrl);
      setWikiData(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong. Please try again.');
    } finally {
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
            className="mt-10 flex flex-col items-center gap-3 text-slate-500"
          >
            <svg className="animate-spin h-8 w-8 text-blue-500" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            <p className="text-sm">Analyzing repository and generating wiki…</p>
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
