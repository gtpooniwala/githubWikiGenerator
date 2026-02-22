'use client';

import { use, useEffect, useState } from 'react';
import Link from 'next/link';
import { generateWiki, GenerateResponse } from '@/lib/api';
import { WikiViewer } from '@/components/WikiViewer';

interface WikiPageProps {
  params: Promise<{ owner: string; repo: string }>;
}

export default function WikiPage({ params }: WikiPageProps) {
  const { owner, repo } = use(params);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [wikiData, setWikiData] = useState<GenerateResponse | null>(null);

  useEffect(() => {
    const repoUrl = `https://github.com/${owner}/${repo}`;
    setLoading(true);
    setError(null);

    generateWiki(repoUrl)
      .then((data) => {
        setWikiData(data);
        setLoading(false);
      })
      .catch((err: Error) => {
        setError(err.message);
        setLoading(false);
      });
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
            <p className="text-sm text-slate-400 mt-1">This may take up to a minute…</p>
          </div>
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
