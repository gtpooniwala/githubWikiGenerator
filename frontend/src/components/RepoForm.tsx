'use client';

import { FormEvent, useState } from 'react';

interface RepoFormProps {
  onSubmit: (repoUrl: string) => void;
  loading: boolean;
}

const PLACEHOLDER = 'https://github.com/owner/repo';
const FEATURED_REPO = 'https://github.com/gtpooniwala/githubWikiGenerator';
const MY_REPOS = [
  'https://github.com/gtpooniwala/pushstart',
  'https://github.com/gtpooniwala/personal-agent',
  'https://github.com/gtpooniwala/LBSchatbot',
  'https://github.com/gtpooniwala/resumebuilder',
];
const EXAMPLE_REPOS = [
  'https://github.com/tastejs/todomvc',
  'https://github.com/browser-use/browser-use',
  'https://github.com/Textualize/rich-cli',
];

export function RepoForm({ onSubmit, loading }: RepoFormProps) {
  const [repoUrl, setRepoUrl] = useState('');

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const url = repoUrl.trim();
    if (!url) return;
    onSubmit(url);
  }

  return (
    <div className="w-full">
      <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-3">
        <input
          type="url"
          id="repo-url-input"
          value={repoUrl}
          onChange={(e) => setRepoUrl(e.target.value)}
          placeholder={PLACEHOLDER}
          required
          disabled={loading}
          aria-label="GitHub repository URL"
          className="flex-1 px-4 py-3 rounded-lg border border-slate-300 bg-white text-slate-900 placeholder-slate-400
            focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
            disabled:opacity-50 disabled:cursor-not-allowed text-sm"
        />
        <button
          type="submit"
          disabled={loading || !repoUrl.trim()}
          className="px-6 py-3 rounded-lg bg-blue-600 text-white font-medium text-sm
            hover:bg-blue-700 active:bg-blue-800
            disabled:opacity-50 disabled:cursor-not-allowed
            transition-colors whitespace-nowrap"
        >
          {loading ? (
            <span className="flex items-center gap-2">
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              Generating…
            </span>
          ) : (
            'Generate Wiki'
          )}
        </button>
      </form>

      {/* Featured recommendation */}
      <div className="mt-4 flex items-center gap-3 px-4 py-3 rounded-lg bg-blue-50 border border-blue-200">
        <span className="text-lg">⭐</span>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-semibold text-blue-800 uppercase tracking-wide mb-0.5">Try it on itself</p>
          <p className="text-xs text-blue-700 truncate">
            Generate a wiki for the very app you&apos;re using right now
          </p>
        </div>
        <button
          type="button"
          disabled={loading}
          onClick={() => setRepoUrl(FEATURED_REPO)}
          className="shrink-0 px-3 py-1.5 rounded-md bg-blue-600 text-white text-xs font-medium
            hover:bg-blue-700 active:bg-blue-800
            disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          Use this repo
        </button>
      </div>

      <div className="mt-3 flex flex-wrap gap-2 items-center">
        <span className="text-xs text-slate-500">More of Gaurav's repos:</span>
        {MY_REPOS.map((repo) => (
          <button
            key={repo}
            type="button"
            disabled={loading}
            onClick={() => setRepoUrl(repo)}
            className="text-xs text-blue-600 hover:underline disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {repo.replace('https://github.com/', '')}
          </button>
        ))}
      </div>

      <div className="mt-2 flex flex-wrap gap-2 items-center">
        <span className="text-xs text-slate-500">Or try:</span>
        {EXAMPLE_REPOS.map((repo) => (
          <button
            key={repo}
            type="button"
            disabled={loading}
            onClick={() => setRepoUrl(repo)}
            className="text-xs text-slate-500 hover:underline disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {repo.replace('https://github.com/', '')}
          </button>
        ))}
      </div>
    </div>
  );
}
