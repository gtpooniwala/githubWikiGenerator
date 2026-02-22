'use client';

import { useCallback, useRef, useState } from 'react';
import { askQuestion, GenerateResponse, WikiFeature } from '@/lib/api';
import { Markdown } from './Markdown';

interface WikiViewerProps {
  data: GenerateResponse;
}

export function WikiViewer({ data }: WikiViewerProps) {
  const features = data.features ?? [];
  const [activeFeatureId, setActiveFeatureId] = useState<string>(
    features.length > 0 ? features[0].id : '__overview__'
  );

  const activeFeature: WikiFeature | undefined = features.find(
    (f) => f.id === activeFeatureId
  );
  const showOverview = activeFeatureId === '__overview__' || features.length === 0;

  const [qaPairs, setQaPairs] = useState<{ question: string; answer: string }[]>([]);
  const [qaInput, setQaInput] = useState('');
  const [qaLoading, setQaLoading] = useState(false);
  const [qaError, setQaError] = useState<string | null>(null);
  const qaHistoryRef = useRef<HTMLDivElement>(null);

  const handleAsk = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      const question = qaInput.trim();
      if (!question || qaLoading) return;
      setQaInput('');
      setQaLoading(true);
      setQaError(null);
      try {
        const result = await askQuestion(question, data);
        setQaPairs((prev) => [...prev, { question, answer: result.answer }]);
        setTimeout(() => {
          if (typeof qaHistoryRef.current?.scrollIntoView === 'function') {
            qaHistoryRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' });
          }
        }, 50);
      } catch (err) {
        setQaError(err instanceof Error ? err.message : 'Failed to get answer');
      } finally {
        setQaLoading(false);
      }
    },
    [qaInput, qaLoading, data],
  );

  return (
    <div className="flex flex-col lg:flex-row border border-slate-200 rounded-xl overflow-hidden bg-white shadow-sm h-full">
      {/* Sidebar */}
      <nav
        aria-label="Wiki sections"
        className="w-full lg:w-72 shrink-0 flex flex-col border-b lg:border-b-0 lg:border-r border-slate-200 bg-slate-50 overflow-hidden"
      >
        {/* Repo info — fixed */}
        <div className="p-4 border-b border-slate-200 shrink-0">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Repository</p>
          <a
            href={`https://github.com/${data.repo_id}`}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-1 text-sm font-semibold text-blue-600 hover:underline break-all"
          >
            {data.repo_id}
          </a>
          <p className="mt-1 text-xs text-slate-400 font-mono truncate" title={data.commit_sha}>
            @ {data.commit_sha.slice(0, 7)}
          </p>
        </div>

        {/* Nav list — scrollable */}
        <ul className="flex-1 overflow-y-auto p-2">
          <li>
            <button
              onClick={() => setActiveFeatureId('__overview__')}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors
                ${showOverview
                  ? 'bg-blue-600 text-white font-medium'
                  : 'text-slate-700 hover:bg-slate-200'
                }`}
            >
              Overview
            </button>
          </li>
          {features.length > 0 && (
            <>
              <li className="px-3 pt-3 pb-1">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Features
                </span>
              </li>
              {features.map((feature) => (
                <li key={feature.id}>
                  <button
                    onClick={() => setActiveFeatureId(feature.id)}
                    title={feature.description}
                    className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors
                      ${activeFeatureId === feature.id
                        ? 'bg-blue-600 text-white font-medium'
                        : 'text-slate-700 hover:bg-slate-200'
                      }`}
                  >
                    {feature.title}
                  </button>
                </li>
              ))}
            </>
          )}
        </ul>

        {/* Q&A panel — pinned at the bottom of the sidebar */}
        <section
          className="shrink-0 border-t border-slate-200 bg-white"
          aria-label="Wiki Q&A"
        >
          <div className="px-3 pt-3 pb-1 flex items-center justify-between">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Ask the wiki</p>
          </div>

          {/* Conversation history */}
          {qaPairs.length > 0 && (
            <div ref={qaHistoryRef} className="max-h-52 overflow-y-auto px-3 pb-2 space-y-3">
              {qaPairs.map((pair, i) => (
                <div key={i} className="text-xs">
                  <p className="font-medium text-slate-700 mb-1">
                    <span className="text-slate-400 mr-0.5" aria-hidden="true">Q:</span>
                    {' '}
                    <span>{pair.question}</span>
                  </p>
                  <div className="pl-2 border-l-2 border-blue-200 text-slate-500 prose prose-xs max-w-none">
                    <Markdown content={pair.answer} />
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Error */}
          {qaError && (
            <div
              role="alert"
              className="mx-3 mb-2 px-2 py-1.5 bg-red-50 border border-red-200 rounded text-xs text-red-700"
            >
              {qaError}
            </div>
          )}

          {/* Input */}
          <form onSubmit={handleAsk} className="flex flex-col gap-1.5 p-3 pt-1">
            <input
              type="text"
              value={qaInput}
              onChange={(e) => setQaInput(e.target.value)}
              placeholder="e.g. How does auth work?"
              disabled={qaLoading}
              aria-label="Ask a question about this wiki"
              className="w-full px-2.5 py-2 rounded-md border border-slate-300 bg-white text-xs
                text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2
                focus:ring-blue-500 focus:border-transparent disabled:opacity-50
                disabled:cursor-not-allowed"
            />
            <button
              type="submit"
              disabled={qaLoading || !qaInput.trim()}
              aria-label={qaLoading ? 'Waiting for answer' : 'Ask question'}
              className="w-full px-3 py-1.5 rounded-md bg-blue-600 text-white text-xs font-medium
                hover:bg-blue-700 active:bg-blue-800 disabled:opacity-50
                disabled:cursor-not-allowed transition-colors"
            >
              {qaLoading ? (
                <span className="flex items-center justify-center gap-1.5">
                  <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  Asking…
                </span>
              ) : (
                'Ask'
              )}
            </button>
          </form>
        </section>
      </nav>

      {/* Content pane — independently scrollable */}
      <main className="flex-1 p-6 lg:p-8 min-w-0 overflow-y-auto">
        {showOverview ? (
          <>
            <h1 className="text-2xl font-bold text-slate-900 mb-4">Overview</h1>
            {data.overview_md ? (
              <Markdown content={data.overview_md} />
            ) : (
              <p className="text-slate-500 italic">No overview available.</p>
            )}
          </>
        ) : activeFeature ? (
          <>
            <h1 className="text-2xl font-bold text-slate-900 mb-2">{activeFeature.title}</h1>
            {activeFeature.description && (
              <p className="text-slate-500 mb-6">{activeFeature.description}</p>
            )}
            <Markdown content={activeFeature.content_md} />
          </>
        ) : null}
      </main>
    </div>
  );
}

