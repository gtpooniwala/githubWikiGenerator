'use client';

import { useCallback, useEffect, useState } from 'react';
import { checkHealth as apiCheckHealth, GenerateResponse } from '@/lib/api';
import { RepoForm } from '@/components/RepoForm';
import { WikiViewer } from '@/components/WikiViewer';

// ── SSE event names ──────────────────────────────────────────────────────────

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

// The 9 events that are true pipeline stages and receive a step number.
// 'connecting' (pre-flight handshake) and 'done' (completion signal) are
// intentionally excluded.
const PIPELINE_STAGES = new Set([
  'repo_loaded',
  'signals_extracted',
  'chunked',
  'import_graph_built',
  'search_index_built',
  'features_proposed',
  'evidence_gathered',
  'pages_written',
  'overview_written',
]);

// ── Types ────────────────────────────────────────────────────────────────────

type Tab = 'home' | 'status' | 'wiki';
type HealthStatus = 'idle' | 'checking' | 'healthy' | 'unhealthy';

interface StatusMessage {
  /** Primary human-readable sentence */
  label: string;
  /** Short summary stat shown inline */
  detail?: string;
  /** Longer text shown in the collapsible section */
  longDetail?: string;
  /** Raw event type, used for the badge */
  eventType: string;
  /** Wall-clock time the event arrived */
  timestamp: Date;
}

// ── Verbose event copy ───────────────────────────────────────────────────────

const EVENT_TITLE: Record<string, string> = {
  connecting:          'Connect to repository',
  repo_loaded:         'Load repository files',
  signals_extracted:   'Extract signals',
  chunked:             'Chunk source files',
  import_graph_built:  'Build import graph',
  search_index_built:  'Build search index',
  features_proposed:   'Propose features',
  evidence_gathered:   'Gather evidence',
  pages_written:       'Write feature pages',
  overview_written:    'Write overview page',
  done:                'Complete',
};

// One or two sentences explaining what the step does and why.
const EVENT_DESCRIPTION: Record<string, string> = {
  connecting:
    'Establishes a connection to the backend and prepares to fetch repository data from GitHub.',
  repo_loaded:
    'Downloads the full file tree and content of the repository from GitHub. ' +
    'Files are fetched in parallel and filtered to exclude binaries, build artefacts, and lock files.',
  signals_extracted:
    'Scans the codebase for structural signals: HTTP route definitions, README headings, and application entrypoints. ' +
    'These signals help the LLM understand what the repository does before reading any code.',
  chunked:
    'Splits every source file into overlapping text segments. ' +
    'Overlapping windows preserve context across chunk boundaries and improve the accuracy of later search and retrieval.',
  import_graph_built:
    'Builds a directed graph of module-level import relationships across the codebase. ' +
    'Used during evidence gathering to find files that are closely related to a given feature.',
  search_index_built:
    'Creates a BM25 keyword search index over all chunks. ' +
    'This index is queried during evidence gathering to surface the most relevant code for each feature.',
  features_proposed:
    'Asks the LLM to identify the key user-facing features of this repository, informed by the signals, README, and file structure. ' +
    'Each proposed feature becomes a dedicated wiki page.',
  evidence_gathered:
    'For each proposed feature, retrieves the most relevant code snippets using the search index and import graph. ' +
    'This grounding evidence is passed to the LLM when writing documentation to minimise hallucination.',
  pages_written:
    'Generates a full documentation page for each feature using the LLM, grounded in the retrieved code evidence. ' +
    'Citations link back to the exact source files used.',
  overview_written:
    'Generates the high-level repository overview using the README, manifest files, and detected entrypoints. ' +
    'This becomes the landing page of the wiki.',
  done:
    'All pipeline stages complete. The wiki is ready to view.',
};

function parseStatusMessage(
  event: string,
  data: Record<string, unknown>,
): Pick<StatusMessage, 'label' | 'detail' | 'longDetail'> {
  const label = EVENT_TITLE[event] ?? event;

  switch (event) {
    case 'repo_loaded': {
      const sha = String(data.commit_sha ?? '').slice(0, 7);
      return {
        label,
        detail: data.file_count != null
          ? `${data.file_count} files scanned · commit ${sha}`
          : undefined,
      };
    }
    case 'chunked':
      return {
        label,
        detail: data.chunk_count != null
          ? `${data.chunk_count} chunks created`
          : undefined,
      };
    case 'signals_extracted': {
      const parts: string[] = [];
      if (data.routes)      parts.push(`${data.routes} routes`);
      if (data.headings)    parts.push(`${data.headings} headings`);
      if (data.entrypoints) parts.push(`${data.entrypoints} entrypoints`);
      return { label, detail: parts.join(' · ') || undefined };
    }
    case 'import_graph_built':
      return {
        label,
        detail: data.edges != null ? `${data.edges} import edges mapped` : undefined,
      };
    case 'search_index_built':
      return {
        label,
        detail: data.indexed_chunks != null
          ? `${data.indexed_chunks} chunks embedded and indexed`
          : undefined,
      };
    case 'features_proposed': {
      if (!Array.isArray(data.features)) return { label };
      const features = data.features as Array<{ title: string }>;
      return {
        label,
        detail: `${features.length} features identified`,
        longDetail: features.map((f, i) => `${i + 1}. ${f.title}`).join('\n'),
      };
    }
    case 'evidence_gathered':
      return {
        label,
        detail: data.feature_count != null
          ? `${data.feature_count} features analyzed`
          : undefined,
      };
    case 'pages_written':
      return {
        label,
        detail: data.page_count != null ? `${data.page_count} pages generated` : undefined,
      };
    default:
      return { label };
  }
}

// ── Sidebar tab definition ───────────────────────────────────────────────────

interface TabDef {
  id: Tab;
  icon: string;
  label: string;
}

const TABS: TabDef[] = [
  { id: 'home',   icon: '🏠', label: 'Home'   },
  { id: 'status', icon: '📊', label: 'Status' },
  { id: 'wiki',   icon: '📖', label: 'Wiki'   },
];

// ── CollapsibleStatusItem ────────────────────────────────────────────────────

function CollapsibleStatusItem({
  msg,
  stepNumber,
  isActive,
  isLoading,
}: {
  msg: StatusMessage;
  stepNumber?: number;   // undefined for connecting / done
  isActive: boolean;
  isLoading: boolean;
}) {
  const [open, setOpen] = useState(false);
  const description = EVENT_DESCRIPTION[msg.eventType];

  return (
    <li>
      {/* ── Row: step number · icon · title · timestamp · Details toggle ── */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-3 py-2.5 text-left group"
        aria-expanded={open}
      >
        {/* Step number pill — or a neutral dot for non-stage events */}
        {stepNumber !== undefined ? (
          <span className={`shrink-0 w-7 h-7 flex items-center justify-center rounded-full text-xs font-bold ${
            isActive && isLoading
              ? 'bg-blue-600 text-white'
              : 'bg-slate-100 text-slate-500'
          }`}>
            {stepNumber}
          </span>
        ) : (
          <span className="shrink-0 w-7 h-7 flex items-center justify-center">
            <span className="w-2 h-2 rounded-full bg-slate-300" />
          </span>
        )}

        {/* Status icon */}
        <span className="shrink-0" aria-hidden="true">
          {isActive && isLoading ? (
            <svg className="animate-spin h-4 w-4 text-blue-500" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
          ) : (
            <svg className="h-4 w-4 text-green-500" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
            </svg>
          )}
        </span>

        {/* Title */}
        <span className={`flex-1 text-sm font-medium ${
          isActive && isLoading ? 'text-blue-700' : 'text-slate-800'
        }`}>
          {msg.label}
        </span>

        {/* Timestamp */}
        <span className="shrink-0 text-[11px] text-slate-400 font-mono">
          {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
        </span>

        {/* Details toggle */}
        <span className="shrink-0 text-xs text-slate-400 group-hover:text-slate-600 transition-colors flex items-center gap-0.5">
          Details
          <svg className={`h-3.5 w-3.5 transition-transform ${open ? 'rotate-180' : ''}`} viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
          </svg>
        </span>
      </button>

      {/* ── Expanded details panel ── */}
      {open && (
        <div className="ml-10 mb-2 pl-4 border-l-2 border-slate-200 space-y-2">
          {/* What this step does */}
          {description && (
            <p className="text-xs text-slate-500 leading-relaxed">{description}</p>
          )}

          {/* Output */}
          {msg.detail && (
            <div className="flex gap-2 text-xs">
              <span className="shrink-0 font-semibold text-slate-400 uppercase tracking-wider">Output</span>
              <span className="text-slate-600">{msg.detail}</span>
            </div>
          )}

          {/* Long detail (e.g. feature list) */}
          {msg.longDetail && (
            <div className="text-xs">
              <p className="font-semibold text-slate-400 uppercase tracking-wider mb-1">Features</p>
              <pre className="whitespace-pre-wrap text-slate-600 leading-relaxed">{msg.longDetail}</pre>
            </div>
          )}
        </div>
      )}

      {/* Divider between steps */}
      <div className="ml-10 border-t border-slate-100" />
    </li>
  );
}

// ── Main page component ───────────────────────────────────────────────────────

export default function Home() {
  const [activeTab, setActiveTab] = useState<Tab>('home');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessages, setStatusMessages] = useState<StatusMessage[]>([]);
  const [healthStatus, setHealthStatus] = useState<HealthStatus>('idle');
  const [wikiData, setWikiData] = useState<GenerateResponse | null>(null);

  // ── Health check ──────────────────────────────────────────────────────────

  const checkHealth = useCallback(async () => {
    setHealthStatus('checking');
    try {
      const data = await apiCheckHealth();
      setHealthStatus(data?.status === 'healthy' ? 'healthy' : 'unhealthy');
    } catch {
      setHealthStatus('unhealthy');
    }
  }, []);

  useEffect(() => { checkHealth(); }, [checkHealth]);

  // ── Generation ────────────────────────────────────────────────────────────

  const handleGenerate = useCallback((repoUrl: string) => {
    setLoading(true);
    setError(null);
    setStatusMessages([]);
    setWikiData(null);
    setActiveTab('status'); // jump to status tab immediately

    const es = new EventSource(`/api/generate/stream?repo_url=${encodeURIComponent(repoUrl)}`);

    SSE_EVENTS.forEach((eventName) => {
      es.addEventListener(eventName, (e: MessageEvent) => {
        let parsed: Record<string, unknown> = {};
        try { parsed = JSON.parse(e.data); } catch { /* ignore */ }

        const { label, detail, longDetail } = parseStatusMessage(eventName, parsed);
        setStatusMessages((prev) => [
          ...prev,
          { label, detail, longDetail, eventType: eventName, timestamp: new Date() },
        ]);

        if (eventName === 'done') {
          es.close();
          setWikiData(parsed as unknown as GenerateResponse);
          setLoading(false);
          setActiveTab('wiki'); // jump to wiki when ready
        }
      });
    });

    es.addEventListener('error', (e: MessageEvent) => {
      let msg = 'Stream error';
      try { msg = JSON.parse(e.data)?.message ?? msg; } catch { /* ignore */ }
      setError(msg);
      es.close();
      setLoading(false);
    });

    // Fallback: connection dropped without a proper SSE error event
    // (e.g. Cloud Run timeout, network blip, container OOM).
    // EventSource automatically retries on CONNECTING state, so only
    // treat CLOSED as a fatal error.
    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) {
        setError(
          'Connection closed unexpectedly — the generation may have taken too long or the server ran out of memory. ' +
          'Try a smaller repository, or try again.'
        );
        setLoading(false);
      }
    };
  }, []);

  // ── Tab availability ──────────────────────────────────────────────────────

  const statusEnabled = loading || statusMessages.length > 0;
  const wikiEnabled   = wikiData !== null;

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-white">

      {/* ── Top header ──────────────────────────────────────────────────── */}
      <header className="shrink-0 border-b border-slate-200 bg-white/90 backdrop-blur-sm z-10">
        <div className="px-4 sm:px-6 py-3 flex items-center gap-3">
          <span className="text-2xl" aria-hidden="true">📚</span>
          <div>
            <h1 className="text-lg font-bold text-slate-900 leading-none">Wiki Generator</h1>
            <p className="text-xs text-slate-500 mt-0.5">Instant feature docs for any public GitHub repo</p>
          </div>

          {/* Health badge + button */}
          <div className="ml-auto flex items-center gap-2">
            {healthStatus !== 'idle' && (
              <span
                aria-label={`Backend status: ${healthStatus}`}
                className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full border ${
                  healthStatus === 'checking'
                    ? 'bg-slate-50 border-slate-200 text-slate-400'
                    : healthStatus === 'healthy'
                    ? 'bg-green-50 border-green-200 text-green-700'
                    : 'bg-red-50 border-red-200 text-red-600'
                }`}
              >
                <span className={`h-1.5 w-1.5 rounded-full ${
                  healthStatus === 'checking'  ? 'bg-slate-300 animate-pulse'
                  : healthStatus === 'healthy' ? 'bg-green-500'
                  : 'bg-red-500'
                }`} />
                {healthStatus === 'checking'
                  ? 'Warming up backend…'
                  : healthStatus === 'healthy'
                  ? 'Backend healthy'
                  : 'Backend unreachable'}
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

      {/* ── Body: sidebar + content ──────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">

        {/* Left sidebar */}
        <nav
          aria-label="Main navigation"
          className="shrink-0 w-52 flex flex-col border-r border-slate-200 bg-slate-50 py-4 gap-1 px-2"
        >
          {TABS.map((tab) => {
            const enabled =
              tab.id === 'home'   ? true :
              tab.id === 'status' ? statusEnabled :
              wikiEnabled;

            const isActive = activeTab === tab.id;

            return (
              <button
                key={tab.id}
                onClick={() => enabled && setActiveTab(tab.id)}
                disabled={!enabled}
                aria-current={isActive ? 'page' : undefined}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors text-left w-full
                  ${isActive
                    ? 'bg-blue-600 text-white shadow-sm'
                    : enabled
                    ? 'text-slate-700 hover:bg-slate-200'
                    : 'text-slate-400 cursor-not-allowed opacity-50'
                  }`}
              >
                <span className="text-base" aria-hidden="true">{tab.icon}</span>
                <span>{tab.label}</span>

                {/* Badges */}
                {tab.id === 'status' && loading && (
                  <span className="ml-auto h-2 w-2 rounded-full bg-blue-400 animate-pulse" />
                )}
                {tab.id === 'status' && !loading && statusMessages.length > 0 && !isActive && (
                  <span className="ml-auto text-[10px] font-semibold bg-slate-200 text-slate-600 rounded-full px-1.5 py-0.5">
                    {statusMessages.length}
                  </span>
                )}
                {tab.id === 'wiki' && wikiEnabled && !isActive && (
                  <span className="ml-auto h-2 w-2 rounded-full bg-green-400" />
                )}
              </button>
            );
          })}

          {/* Divider + repo form shortcut when not on home */}
          {activeTab !== 'home' && (
            <div className="mt-auto pt-4 border-t border-slate-200">
              <p className="px-3 pb-1 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                New generation
              </p>
              <button
                onClick={() => setActiveTab('home')}
                className="w-full text-left px-3 py-2 rounded-lg text-xs text-slate-600 hover:bg-slate-200 transition-colors"
              >
                ← Back to Home
              </button>
            </div>
          )}
        </nav>

        {/* Main content pane */}
        <main className="flex-1 overflow-hidden flex flex-col">

          {/* ── TAB: Home ─────────────────────────────────────────────── */}
          {activeTab === 'home' && (
            <div className="flex-1 overflow-y-auto bg-gradient-to-b from-slate-50 to-white">
              <section className="max-w-3xl mx-auto px-6 py-14">
                <div className="text-center mb-10">
                  <h2 className="text-3xl sm:text-4xl font-bold text-slate-900 mb-3">
                    Generate developer docs in one click
                  </h2>
                  <p className="text-slate-500 text-lg max-w-xl mx-auto">
                    Paste a public GitHub repository URL and get a navigable wiki organised by user-facing features.
                  </p>
                </div>
                <RepoForm onSubmit={handleGenerate} loading={loading} />
                {error && (
                  <div role="alert" className="mt-6 p-4 bg-red-50 border border-red-200 rounded-lg flex gap-3 text-sm text-red-700">
                    <span className="shrink-0">❌</span>
                    <span>{error}</span>
                  </div>
                )}
              </section>
            </div>
          )}

          {/* ── TAB: Status ───────────────────────────────────────────── */}
          {activeTab === 'status' && (
            <div className="flex-1 overflow-y-auto bg-slate-50">
              <div className="max-w-2xl mx-auto px-6 py-8">
                {/* Header row */}
                <div className="flex items-center justify-between mb-6">
                  <div>
                    <h2 className="text-xl font-bold text-slate-900">Generation log</h2>
                    <p className="text-sm text-slate-500 mt-0.5">
                      {loading
                        ? 'Pipeline is running…'
                        : statusMessages.length > 0
                        ? `Completed in ${statusMessages.length} steps`
                        : 'No generation started yet'}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                  {loading && (
                    <>
                      <button
                        disabled
                        aria-label="Generating wiki"
                        className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-100 text-blue-700 text-sm font-medium cursor-not-allowed"
                      >
                        <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                        </svg>
                        Generating…
                      </button>
                    </>
                  )}
                  {!loading && wikiEnabled && (
                    <button
                      onClick={() => setActiveTab('wiki')}
                      className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-colors"
                    >
                      View Wiki →
                    </button>
                  )}
                  </div>
                </div>

                {/* Error banner */}
                {error && (
                  <div role="alert" className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg flex gap-3 text-sm text-red-700">
                    <span className="shrink-0">❌</span>
                    <span>{error}</span>
                  </div>
                )}

                {/* Accessible loading status for assistive technology */}
                {loading && (
                  <div
                    role="status"
                    aria-label="Generating wiki"
                    className="sr-only"
                  />
                )}

                {statusMessages.length === 0 && !loading ? (
                  <div className="text-center py-20 text-slate-400">
                    <p className="text-4xl mb-3">📊</p>
                    <p className="text-sm">Start a generation from the <strong>Home</strong> tab to see live progress here.</p>
                  </div>
                ) : (
                  <ul>
                    {(() => {
                      let step = 0;
                      return statusMessages.map((msg, i) => {
                        const isStage = PIPELINE_STAGES.has(msg.eventType);
                        if (isStage) step++;
                        return (
                          <CollapsibleStatusItem
                            key={i}
                            msg={msg}
                            stepNumber={isStage ? step : undefined}
                            isActive={i === statusMessages.length - 1}
                            isLoading={loading}
                          />
                        );
                      });
                    })()}
                    {/* Trailing placeholder while loading and no events yet */}
                    {loading && statusMessages.length === 0 && (
                      <li className="px-4 py-3 rounded-lg border border-blue-200 bg-blue-50 text-sm text-blue-600 font-medium flex items-center gap-3">
                        <svg className="animate-spin h-4 w-4 text-blue-500 shrink-0" viewBox="0 0 24 24" fill="none">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                        </svg>
                        Connecting to pipeline…
                      </li>
                    )}
                  </ul>
                )}
              </div>
            </div>
          )}

          {/* ── TAB: Wiki ─────────────────────────────────────────────── */}
          {activeTab === 'wiki' && (
            wikiData ? (
              <div className="flex-1 overflow-hidden px-4 sm:px-6 py-4">
                <WikiViewer data={wikiData} />
              </div>
            ) : (
              <div className="flex-1 flex items-center justify-center text-slate-400">
                <div className="text-center">
                  <p className="text-4xl mb-3">📖</p>
                  <p className="text-sm">No wiki generated yet. Start from the <strong>Home</strong> tab.</p>
                </div>
              </div>
            )
          )}

        </main>
      </div>
    </div>
  );
}
