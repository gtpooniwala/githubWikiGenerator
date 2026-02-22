'use client';

import { useState } from 'react';
import { GenerateResponse, WikiFeature } from '@/lib/api';
import { Markdown } from './Markdown';

interface WikiViewerProps {
  data: GenerateResponse;
}

export function WikiViewer({ data }: WikiViewerProps) {
  const [activeFeatureId, setActiveFeatureId] = useState<string>(
    data.features.length > 0 ? data.features[0].id : '__overview__'
  );

  const activeFeature: WikiFeature | undefined = data.features.find(
    (f) => f.id === activeFeatureId
  );
  const showOverview = activeFeatureId === '__overview__';

  return (
    <div className="flex flex-col lg:flex-row gap-0 border border-slate-200 rounded-xl overflow-hidden bg-white shadow-sm">
      {/* Sidebar */}
      <nav
        aria-label="Wiki sections"
        className="w-full lg:w-64 shrink-0 border-b lg:border-b-0 lg:border-r border-slate-200 bg-slate-50"
      >
        <div className="p-4 border-b border-slate-200">
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

        <ul className="p-2">
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
          {data.features.length > 0 && (
            <>
              <li className="px-3 pt-3 pb-1">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Features
                </span>
              </li>
              {data.features.map((feature) => (
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
      </nav>

      {/* Content pane */}
      <main className="flex-1 p-6 lg:p-8 min-w-0 overflow-auto">
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
