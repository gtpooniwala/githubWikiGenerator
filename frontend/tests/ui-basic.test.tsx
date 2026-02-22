// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { GenerateResponse } from '@/lib/api';

// Mock the api module (used by page.tsx)
vi.mock('@/lib/api', () => ({
  checkHealth: vi.fn().mockResolvedValue({ status: 'healthy' }),
  generateWiki: vi.fn(),
}));

import { generateWiki } from '@/lib/api';
import Home from '../src/app/page';
import { RepoForm } from '../src/components/RepoForm';

// ---------------------------------------------------------------------------
// Minimal EventSource mock — jsdom doesn't include EventSource
// ---------------------------------------------------------------------------
class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  onerror: (() => void) | null = null;
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

  close() {}
}

// Silence real fetch calls (warm-up health check)
beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 200 })));
  vi.stubGlobal('EventSource', MockEventSource);
  MockEventSource.instances = [];
  vi.clearAllMocks();
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

  it('fires warm-up health fetch on mount', () => {
    render(<Home />);
    expect(vi.mocked(fetch)).toHaveBeenCalledWith('/api/health');
  });

  it('shows loading state while generate is in progress', async () => {
    const user = userEvent.setup();

    // Return a promise that never resolves so we stay in loading state
    vi.mocked(generateWiki).mockReturnValue(new Promise(() => {}));

    render(<Home />);

    const input = screen.getByRole('textbox', { name: /github repository url/i });
    await user.type(input, 'https://github.com/owner/repo');
    await user.click(screen.getByRole('button', { name: /generate wiki/i }));

    expect(screen.getByRole('status', { name: /generating wiki/i })).toBeInTheDocument();
    // submit button should be disabled while loading
    expect(screen.getByRole('button', { name: /generating/i })).toBeDisabled();
  });

  it('displays wiki viewer after successful generation', async () => {
    const user = userEvent.setup();

    vi.mocked(generateWiki).mockResolvedValue({
      repo_id: 'owner/repo',
      commit_sha: 'abc1234def5678',
      overview_md: '# My Overview\n\nSome overview text.',
      features: [
        {
          id: 'auth',
          title: 'Authentication',
          description: 'Handles user auth',
          content_md: '## Auth details here',
        },
      ],
    });

    render(<Home />);

    const input = screen.getByRole('textbox', { name: /github repository url/i });
    await user.type(input, 'https://github.com/owner/repo');
    await user.click(screen.getByRole('button', { name: /generate wiki/i }));

    await waitFor(() => {
      // sidebar nav + content heading both contain 'Authentication'; checking the heading is enough
      expect(screen.getByRole('heading', { name: /authentication/i, level: 1 })).toBeInTheDocument();
    });

    expect(screen.getByText('owner/repo')).toBeInTheDocument();
  });

  it('shows error message when generate fails', async () => {
    const user = userEvent.setup();

    vi.mocked(generateWiki).mockRejectedValue(new Error('Network error'));

    render(<Home />);

    const input = screen.getByRole('textbox', { name: /github repository url/i });
    await user.type(input, 'https://github.com/owner/repo');
    await user.click(screen.getByRole('button', { name: /generate wiki/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    expect(screen.getByRole('alert')).toHaveTextContent('Network error');
  });

  it('displays SSE status messages as events arrive', async () => {
    const user = userEvent.setup();

    // generateWiki never resolves so we stay in the loading state
    vi.mocked(generateWiki).mockReturnValue(new Promise(() => {}));

    render(<Home />);

    const input = screen.getByRole('textbox', { name: /github repository url/i });
    await user.type(input, 'https://github.com/owner/repo');
    await user.click(screen.getByRole('button', { name: /generate wiki/i }));

    // Retrieve the MockEventSource created during handleGenerate
    const es = MockEventSource.instances[0];
    expect(es).toBeDefined();
    expect(es.url).toContain('repo_url=');
    expect(es.url).toContain(encodeURIComponent('https://github.com/owner/repo'));

    act(() => es.emit('repo_loaded', { message: 'Repository loaded' }));
    await waitFor(() => expect(screen.getByText(/repository loaded/i)).toBeInTheDocument());

    act(() => es.emit('chunked', { message: 'Files chunked' }));
    await waitFor(() => expect(screen.getByText(/files chunked/i)).toBeInTheDocument());
  });
});
