// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// Mock the api module
vi.mock('@/lib/api', () => ({
  checkHealth: vi.fn().mockResolvedValue({ status: 'healthy' }),
  // Default: never-resolving promise so tests control when wiki data arrives
  generateWiki: vi.fn(() => new Promise(() => {})),
  // Default: pending — individual tests override as needed
  askQuestion: vi.fn(() => new Promise(() => {})),
}));

import { checkHealth, generateWiki, askQuestion } from '@/lib/api';
import Home from '../src/app/page';
import { RepoForm } from '../src/components/RepoForm';
import { WikiViewer } from '../src/components/WikiViewer';

// ---------------------------------------------------------------------------
// MockEventSource — jsdom doesn't include EventSource
// ---------------------------------------------------------------------------
class MockEventSource {
  static instances: MockEventSource[] = [];
  static OPEN = 1;
  static CLOSED = 2;

  url: string;
  readyState = MockEventSource.OPEN;
  onerror: ((e?: Event) => void) | null = null;
  private listeners: Record<string, Array<(e: { data: string }) => void>> = {};

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(event: string, handler: (e: { data: string }) => void) {
    if (!this.listeners[event]) this.listeners[event] = [];
    this.listeners[event].push(handler);
  }

  emit(event: string, data: Record<string, unknown> = {}) {
    this.listeners[event]?.forEach((h) => h({ data: JSON.stringify(data) }));
  }

  close() {
    this.readyState = MockEventSource.CLOSED;
  }
}

// Shared mock wiki response used in several tests
const MOCK_WIKI = {
  repo_id: 'owner/repo',
  commit_sha: 'abc1234def567',
  overview_md: '## Overview\n\nThis is the overview.',
  features: [
    {
      id: 'feature-one',
      title: 'Feature One',
      description: 'The first feature.',
      content_md: '## Feature One\n\nContent here.',
    },
  ],
};

// ---------------------------------------------------------------------------
// Shared setup
// ---------------------------------------------------------------------------
beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 200 })));
  vi.stubGlobal('EventSource', MockEventSource);
  MockEventSource.instances = [];
  vi.clearAllMocks();
  // Re-apply after clearAllMocks
  vi.mocked(checkHealth).mockResolvedValue({ status: 'healthy' });
  vi.mocked(generateWiki).mockImplementation(() => new Promise(() => {})); // pending by default
});

describe('RepoForm', () => {
  it('renders the URL input and submit button', () => {
    render(<RepoForm onSubmit={vi.fn()} loading={false} />);
    expect(screen.getByRole('textbox', { name: /github repository url/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /generate wiki/i })).toBeInTheDocument();
  });

  it('calls onSubmit with trimmed URL when form is submitted', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<RepoForm onSubmit={onSubmit} loading={false} />);

    const input = screen.getByRole('textbox', { name: /github repository url/i });
    await user.type(input, '  https://github.com/owner/repo  ');
    await user.click(screen.getByRole('button', { name: /generate wiki/i }));

    expect(onSubmit).toHaveBeenCalledOnce();
    expect(onSubmit).toHaveBeenCalledWith('https://github.com/owner/repo');
  });

  it('disables input and button while loading', () => {
    render(<RepoForm onSubmit={vi.fn()} loading={true} />);
    expect(screen.getByRole('textbox', { name: /github repository url/i })).toBeDisabled();
    // all buttons (submit + example shortcuts) are disabled while loading
    const buttons = screen.getAllByRole('button');
    buttons.forEach((btn) => expect(btn).toBeDisabled());
  });

  it('shows "Generating…" text in button while loading', () => {
    render(<RepoForm onSubmit={vi.fn()} loading={true} />);
    expect(screen.getByRole('button', { name: /generating/i })).toBeInTheDocument();
  });

  it('fills input when example repo is clicked', async () => {
    const user = userEvent.setup();
    render(<RepoForm onSubmit={vi.fn()} loading={false} />);

    await user.click(screen.getByRole('button', { name: /tastejs\/todomvc/i }));
    const input = screen.getByRole<HTMLInputElement>('textbox', { name: /github repository url/i });
    expect(input.value).toBe('https://github.com/tastejs/todomvc');
  });
});

describe('Home page', () => {
  it('renders the heading and form on load', () => {
    render(<Home />);
    expect(screen.getByRole('heading', { name: /generate developer docs/i })).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: /github repository url/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /generate wiki/i })).toBeInTheDocument();
  });

  it('calls checkHealth on mount for warm-up', () => {
    render(<Home />);
    expect(vi.mocked(checkHealth)).toHaveBeenCalledOnce();
  });

  it('shows backend healthy indicator after successful health check', async () => {
    render(<Home />);
    await waitFor(() => expect(screen.getByText(/backend healthy/i)).toBeInTheDocument());
  });

  it('shows backend unreachable indicator when health check fails', async () => {
    vi.mocked(checkHealth).mockRejectedValueOnce(new Error('connection refused'));
    render(<Home />);
    await waitFor(() => expect(screen.getByText(/backend unreachable/i)).toBeInTheDocument());
  });

  it('shows loading state while SSE stream is in progress', async () => {
    const user = userEvent.setup();

    render(<Home />);

    const input = screen.getByRole('textbox', { name: /github repository url/i });
    await user.type(input, 'https://github.com/owner/repo');
    await user.click(screen.getByRole('button', { name: /generate wiki/i }));

    // SSE is open but no events emitted yet — loading spinner should show
    expect(screen.getByRole('status', { name: /generating wiki/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /generating/i })).toBeDisabled();
  });

  it('stops loading and renders wiki immediately when done event carries full payload', async () => {
    const user = userEvent.setup();
    render(<Home />);

    const input = screen.getByRole('textbox', { name: /github repository url/i });
    await user.type(input, 'https://github.com/owner/repo');
    await user.click(screen.getByRole('button', { name: /generate wiki/i }));

    const es = MockEventSource.instances[0];
    // done now carries the full GenerateResponse — no second POST needed
    act(() => es.emit('done', MOCK_WIKI));

    await waitFor(() => {
      expect(screen.queryByRole('status', { name: /generating wiki/i })).not.toBeInTheDocument();
    });
    expect(screen.getByRole('link', { name: /owner\/repo/i })).toBeInTheDocument();
  });

  it('shows wiki viewer when done event carries full wiki payload', async () => {
    const user = userEvent.setup();
    render(<Home />);

    const input = screen.getByRole('textbox', { name: /github repository url/i });
    await user.type(input, 'https://github.com/owner/repo');
    await user.click(screen.getByRole('button', { name: /generate wiki/i }));

    const es = MockEventSource.instances[0];
    // done payload IS the GenerateResponse — wiki renders immediately, no POST
    act(() => es.emit('done', MOCK_WIKI));

    await waitFor(() => {
      // WikiViewer renders the repo link in the sidebar
      expect(screen.getByRole('link', { name: /owner\/repo/i })).toBeInTheDocument();
    });

    // Loading spinner should be gone
    expect(screen.queryByRole('status', { name: /generating wiki/i })).not.toBeInTheDocument();
  });

  it('shows wiki sidebar with overview and feature list', async () => {
    vi.mocked(generateWiki).mockResolvedValueOnce(MOCK_WIKI);
    const user = userEvent.setup();
    render(<Home />);

    await user.type(
      screen.getByRole('textbox', { name: /github repository url/i }),
      'https://github.com/owner/repo',
    );
    await user.click(screen.getByRole('button', { name: /generate wiki/i }));

    const es = MockEventSource.instances[0];
    // done carries the full GenerateResponse
    act(() => es.emit('done', MOCK_WIKI));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /overview/i })).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /feature one/i })).toBeInTheDocument();
  });

  it('shows error message when SSE error event fires', async () => {
    const user = userEvent.setup();

    render(<Home />);

    const input = screen.getByRole('textbox', { name: /github repository url/i });
    await user.type(input, 'https://github.com/owner/repo');
    await user.click(screen.getByRole('button', { name: /generate wiki/i }));

    const es = MockEventSource.instances[0];
    act(() => es.emit('error', { message: 'Rate limit exceeded' }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    expect(screen.getByRole('alert')).toHaveTextContent('Rate limit exceeded');
  });

  it('creates EventSource with encoded repo_url and displays events with details', async () => {
    const user = userEvent.setup();
    render(<Home />);

    await user.type(
      screen.getByRole('textbox', { name: /github repository url/i }),
      'https://github.com/owner/repo',
    );
    await user.click(screen.getByRole('button', { name: /generate wiki/i }));

    const es = MockEventSource.instances[0];
    expect(es).toBeDefined();
    expect(es.url).toContain('repo_url=');
    expect(es.url).toContain(encodeURIComponent('https://github.com/owner/repo'));

    act(() => es.emit('repo_loaded', { message: 'Repository loaded', file_count: 42, commit_sha: 'abc1234' }));
    await waitFor(() => expect(screen.getByText(/repository loaded/i)).toBeInTheDocument());
    expect(screen.getByText(/42 files/)).toBeInTheDocument();

    act(() => es.emit('chunked', { message: 'Files chunked', chunk_count: 99 }));
    await waitFor(() => expect(screen.getByText(/files chunked/i)).toBeInTheDocument());
    expect(screen.getByText(/99 chunks/)).toBeInTheDocument();

    act(() => es.emit('signals_extracted', { message: 'Signals extracted', routes: 5, headings: 8, entrypoints: 2 }));
    await waitFor(() => expect(screen.getByText(/signals extracted/i)).toBeInTheDocument());
    expect(screen.getByText(/5 routes/)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// WikiViewer — Q&A panel
// ---------------------------------------------------------------------------

describe('WikiViewer Q&A', () => {
  function renderViewer() {
    return render(<WikiViewer data={MOCK_WIKI} />);
  }

  beforeEach(() => {
    vi.mocked(askQuestion).mockReset();
    vi.mocked(askQuestion).mockImplementation(() => new Promise(() => {})); // pending by default
  });

  it('renders the Q&A section heading and input', () => {
    renderViewer();
    expect(screen.getByRole('region', { name: /wiki q&a/i })).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: /ask a question about this wiki/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /ask question/i })).toBeInTheDocument();
  });

  it('Ask button is disabled when input is empty', () => {
    renderViewer();
    const btn = screen.getByRole('button', { name: /ask question/i });
    expect(btn).toBeDisabled();
  });

  it('Ask button is enabled when input has text', async () => {
    const user = userEvent.setup();
    renderViewer();
    await user.type(
      screen.getByRole('textbox', { name: /ask a question about this wiki/i }),
      'How does auth work?',
    );
    expect(screen.getByRole('button', { name: /ask question/i })).not.toBeDisabled();
  });

  it('calls askQuestion with the question and wiki data when submitted', async () => {
    vi.mocked(askQuestion).mockResolvedValueOnce({ answer: 'Auth uses JWT.' });
    const user = userEvent.setup();
    renderViewer();

    await user.type(
      screen.getByRole('textbox', { name: /ask a question about this wiki/i }),
      'How does auth work?',
    );
    await user.click(screen.getByRole('button', { name: /ask question/i }));

    expect(vi.mocked(askQuestion)).toHaveBeenCalledOnce();
    expect(vi.mocked(askQuestion)).toHaveBeenCalledWith(
      'How does auth work?',
      MOCK_WIKI,
    );
  });

  it('displays the answer after a successful askQuestion call', async () => {
    vi.mocked(askQuestion).mockResolvedValueOnce({ answer: 'Auth uses JWT tokens.' });
    const user = userEvent.setup();
    renderViewer();

    await user.type(
      screen.getByRole('textbox', { name: /ask a question about this wiki/i }),
      'How does auth work?',
    );
    await user.click(screen.getByRole('button', { name: /ask question/i }));

    await waitFor(() =>
      expect(screen.getByText(/auth uses jwt tokens\./i)).toBeInTheDocument(),
    );
    // The question should also appear in the history
    expect(screen.getByText('How does auth work?')).toBeInTheDocument();
  });

  it('shows an error alert when askQuestion rejects', async () => {
    vi.mocked(askQuestion).mockRejectedValueOnce(new Error('Rate limit hit'));
    const user = userEvent.setup();
    renderViewer();

    await user.type(
      screen.getByRole('textbox', { name: /ask a question about this wiki/i }),
      'What is this?',
    );
    await user.click(screen.getByRole('button', { name: /ask question/i }));

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
    expect(screen.getByRole('alert')).toHaveTextContent('Rate limit hit');
  });

  it('disables input and shows loading state while waiting for answer', async () => {
    // Keep askQuestion pending indefinitely
    vi.mocked(askQuestion).mockImplementation(() => new Promise(() => {}));
    const user = userEvent.setup();
    renderViewer();

    await user.type(
      screen.getByRole('textbox', { name: /ask a question about this wiki/i }),
      'What is this repo?',
    );
    await user.click(screen.getByRole('button', { name: /ask question/i }));

    // Input should be disabled while loading
    expect(
      screen.getByRole('textbox', { name: /ask a question about this wiki/i }),
    ).toBeDisabled();
    // Button shows "Asking…" or "Waiting for answer" aria-label
    expect(screen.getByRole('button', { name: /waiting for answer/i })).toBeInTheDocument();
  });

  it('accumulates multiple Q&A pairs in the history', async () => {
    vi.mocked(askQuestion)
      .mockResolvedValueOnce({ answer: 'First answer.' })
      .mockResolvedValueOnce({ answer: 'Second answer.' });

    const user = userEvent.setup();
    renderViewer();

    const input = screen.getByRole('textbox', { name: /ask a question about this wiki/i });

    await user.type(input, 'Q1');
    await user.click(screen.getByRole('button', { name: /ask question/i }));
    await waitFor(() => expect(screen.getByText('First answer.')).toBeInTheDocument());

    await user.type(input, 'Q2');
    await user.click(screen.getByRole('button', { name: /ask question/i }));
    await waitFor(() => expect(screen.getByText('Second answer.')).toBeInTheDocument());

    // Both questions and answers should be in the history
    expect(screen.getByText('Q1')).toBeInTheDocument();
    expect(screen.getByText('Q2')).toBeInTheDocument();
  });
});
