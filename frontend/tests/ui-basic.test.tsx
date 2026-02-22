// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// Mock the api module
vi.mock('@/lib/api', () => ({
  checkHealth: vi.fn().mockResolvedValue({ status: 'healthy' }),
  // Default: never-resolving promise so tests control when wiki data arrives
  generateWiki: vi.fn(() => new Promise(() => {})),
}));

import { checkHealth, generateWiki } from '@/lib/api';
import Home from '../src/app/page';
import { RepoForm } from '../src/components/RepoForm';

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

  it('shows loading spinner while generateWiki is pending after SSE done', async () => {
    // generateWiki is pending by default
    const user = userEvent.setup();
    render(<Home />);

    const input = screen.getByRole('textbox', { name: /github repository url/i });
    await user.type(input, 'https://github.com/owner/repo');
    await user.click(screen.getByRole('button', { name: /generate wiki/i }));

    const es = MockEventSource.instances[0];
    act(() => es.emit('done', { message: 'Complete' }));

    // Loading spinner should still be present while generateWiki is pending
    await waitFor(() => {
      expect(screen.getByRole('status', { name: /generating wiki/i })).toBeInTheDocument();
    });
  });

  it('shows wiki viewer when generateWiki resolves after SSE done', async () => {
    vi.mocked(generateWiki).mockResolvedValueOnce(MOCK_WIKI);
    const user = userEvent.setup();
    render(<Home />);

    const input = screen.getByRole('textbox', { name: /github repository url/i });
    await user.type(input, 'https://github.com/owner/repo');
    await user.click(screen.getByRole('button', { name: /generate wiki/i }));

    const es = MockEventSource.instances[0];
    act(() => es.emit('done', { message: 'Complete' }));

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
    act(() => es.emit('done', { message: 'Complete' }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /overview/i })).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /feature one/i })).toBeInTheDocument();
  });

  it('shows error message when generateWiki fails after SSE done', async () => {
    vi.mocked(generateWiki).mockRejectedValueOnce(new Error('OpenAI rate limit'));
    const user = userEvent.setup();
    render(<Home />);

    await user.type(
      screen.getByRole('textbox', { name: /github repository url/i }),
      'https://github.com/owner/repo',
    );
    await user.click(screen.getByRole('button', { name: /generate wiki/i }));

    const es = MockEventSource.instances[0];
    act(() => es.emit('done', { message: 'Complete' }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('OpenAI rate limit');
    });
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
