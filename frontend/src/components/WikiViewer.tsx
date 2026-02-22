'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { askQuestion, GenerateResponse, WikiFeature } from '@/lib/api';
import { Markdown } from './Markdown';

const ASK_ID = '__ask__';
const OVERVIEW_ID = '__overview__';

interface WikiViewerProps {
  data: GenerateResponse;
}

export function WikiViewer({ data }: WikiViewerProps) {
  const features = data.features ?? [];
  const [activeId, setActiveId] = useState<string>(
    features.length > 0 ? features[0].id : OVERVIEW_ID,
  );

  const activeFeature: WikiFeature | undefined = features.find((f) => f.id === activeId);
  const showOverview = activeId === OVERVIEW_ID || (features.length === 0 && activeId !== ASK_ID);
  const showAsk = activeId === ASK_ID;

  // ── Q&A state ──────────────────────────────────────────────────────────────
  const [qaPairs, setQaPairs] = useState<{ question: string; answer: string }[]>([]);
  const [qaInput, setQaInput] = useState('');
  const [qaLoading, setQaLoading] = useState(false);
  const [qaError, setQaError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Focus input whenever the Ask tab is opened
  useEffect(() => {
    if (showAsk) {
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [showAsk]);

  // Scroll to bottom after each new answer
  useEffect(() => {
    if (bottomRef.current && typeof bottomRef.current.scrollIntoView === 'function') {
      bottomRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
  }, [qaPairs.length]);

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
      {/* ── Sidebar ────────────────────────────────────────────────────────── */}
      <nav
        aria-label="Wiki sections"
        className="w-full lg:w-72 shrink-0 flex flex-col border-b lg:border-b-0 lg:border-r border-slate-200 bg-slate-50"
      >
        {/* Repo info */}
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

        {/* Scrollable page list */}
        <ul className="flex-1 overflow-y-auto p-2">
          <li>
            <button
              onClick={() => setActiveId(OVERVIEW_ID)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                showOverview
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
                    onClick={() => setActiveId(feature.id)}
                    title={feature.description}
                    className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                      activeId === feature.id
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

        {/* ── "Ask the wiki" — pinned to bottom of sidebar ──────────────── */}
        <div className="shrink-0 p-2 border-t border-slate-200">
          <button
            onClick={() => setActiveId(ASK_ID)}
            className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
              showAsk
                ? 'bg-indigo-600 text-white shadow-sm'
                : 'bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200'
            }`}
          >
            {/* Chat bubble icon */}
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
              className="h-4 w-4 shrink-0"
              aria-hidden="true"
            >
              <path
                fillRule="evenodd"
                d="M10 2c-2.236 0-4.43.18-6.57.524C1.993 2.755 1 4.014 1 5.426v5.148c0 1.413.993 2.67 2.43 2.902.848.137 1.705.248 2.57.331v3.443a.75.75 0 001.28.53l3.58-3.579a.78.78 0 01.527-.224 41.202 41.202 0 005.183-.5c1.437-.232 2.43-1.49 2.43-2.903V5.426c0-1.413-.993-2.67-2.43-2.902A41.289 41.289 0 0010 2zm0 7a1 1 0 100-2 1 1 0 000 2zM6 9a1 1 0 11-2 0 1 1 0 012 0zm5 1a1 1 0 100-2 1 1 0 000 2z"
                clipRule="evenodd"
              />
            </svg>
            Ask the wiki
            {qaPairs.length > 0 && (
              <span
                className={`ml-auto text-xs font-mono px-1.5 py-0.5 rounded-full ${
                  showAsk ? 'bg-indigo-500 text-indigo-100' : 'bg-indigo-200 text-indigo-700'
                }`}
              >
                {qaPairs.length}
              </span>
            )}
          </button>
        </div>
      </nav>

      {/* ── Content pane ───────────────────────────────────────────────────── */}
      {showAsk ? (
        /* Ask page — flex column so input bar can be pinned at the bottom */
        <div className="flex-1 min-w-0 flex flex-col overflow-hidden">
          {/* Scrollable Q&A history */}
          <div className="flex-1 overflow-y-auto px-6 lg:px-8 py-6 space-y-10">
            {/* Empty state */}
            {qaPairs.length === 0 && !qaLoading && (
              <div className="flex flex-col items-center justify-center h-full text-center py-20">
                <div className="h-12 w-12 rounded-full bg-indigo-100 flex items-center justify-center mb-4">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                    className="h-6 w-6 text-indigo-500"
                    aria-hidden="true"
                  >
                    <path
                      fillRule="evenodd"
                      d="M10 2c-2.236 0-4.43.18-6.57.524C1.993 2.755 1 4.014 1 5.426v5.148c0 1.413.993 2.67 2.43 2.902.848.137 1.705.248 2.57.331v3.443a.75.75 0 001.28.53l3.58-3.579a.78.78 0 01.527-.224 41.202 41.202 0 005.183-.5c1.437-.232 2.43-1.49 2.43-2.903V5.426c0-1.413-.993-2.67-2.43-2.902A41.289 41.289 0 0010 2zm0 7a1 1 0 100-2 1 1 0 000 2zM6 9a1 1 0 11-2 0 1 1 0 012 0zm5 1a1 1 0 100-2 1 1 0 000 2z"
                      clipRule="evenodd"
                    />
                  </svg>
                </div>
                <h2 className="text-lg font-semibold text-slate-700 mb-1">Ask the wiki</h2>
                <p className="text-sm text-slate-400 max-w-xs">
                  Ask any question about this repository. Answers are grounded in the generated documentation.
                </p>
              </div>
            )}

            {/* Question / answer pairs */}
            {qaPairs.map((pair, i) => (
              <article key={i}>
                {/* Question — styled like a page heading */}
                <div className="flex items-start gap-3 mb-4">
                  <span className="shrink-0 mt-1 h-6 w-6 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 text-xs font-bold select-none">
                    Q
                  </span>
                  <h2 className="text-xl font-bold text-slate-900 leading-snug">{pair.question}</h2>
                </div>

                {/* Answer — full Markdown, same as feature pages */}
                <div className="pl-9 prose prose-sm prose-slate max-w-none border-l-2 border-indigo-100">
                  <Markdown content={pair.answer} />
                </div>

                {i < qaPairs.length - 1 && <hr className="mt-10 border-slate-100" />}
              </article>
            ))}

            {/* Loading indicator */}
            {qaLoading && (
              <article>
                <div className="flex items-start gap-3 mb-4">
                  <span className="shrink-0 mt-1 h-6 w-6 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 text-xs font-bold select-none">
                    Q
                  </span>
                  <h2 className="text-xl font-bold text-slate-900 leading-snug opacity-50">…</h2>
                </div>
                <div className="pl-9 flex items-center gap-2 text-slate-400 text-sm">
                  <svg className="animate-spin h-4 w-4 text-indigo-400" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  Thinking…
                </div>
              </article>
            )}

            {/* Scroll anchor */}
            <div ref={bottomRef} />
          </div>

          {/* Pinned input bar */}
          <div className="shrink-0 border-t border-slate-200 bg-white px-6 lg:px-8 py-4">
            {qaError && (
              <div role="alert" className="mb-3 px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                {qaError}
              </div>
            )}
            <form onSubmit={handleAsk} className="flex gap-3">
              <input
                ref={inputRef}
                type="text"
                value={qaInput}
                onChange={(e) => setQaInput(e.target.value)}
                placeholder="Ask a question about this repository…"
                disabled={qaLoading}
                aria-label="Ask a question about this wiki"
                className="flex-1 px-4 py-2.5 rounded-lg border border-slate-300 bg-white text-sm
                  text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2
                  focus:ring-indigo-500 focus:border-transparent disabled:opacity-50
                  disabled:cursor-not-allowed"
              />
              <button
                type="submit"
                disabled={qaLoading || !qaInput.trim()}
                aria-label={qaLoading ? 'Waiting for answer' : 'Ask question'}
                className="shrink-0 px-5 py-2.5 rounded-lg bg-indigo-600 text-white text-sm font-medium
                  hover:bg-indigo-700 active:bg-indigo-800 disabled:opacity-50
                  disabled:cursor-not-allowed transition-colors flex items-center gap-2"
              >
                {qaLoading ? (
                  <>
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                    </svg>
                    Asking…
                  </>
                ) : (
                  'Ask'
                )}
              </button>
            </form>
          </div>
        </div>
      ) : (
        /* Regular wiki page — independently scrollable */
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
      )}
    </div>
  );
}
