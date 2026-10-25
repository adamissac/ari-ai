import { afterEach, describe, expect, it, vi } from 'vitest';

const { liveAnalysisMock } = vi.hoisted(() => ({ liveAnalysisMock: vi.fn() }));

vi.mock('server-only', () => ({}));
vi.mock('@/lib/live-analysis', () => ({
  LiveError: class LiveError extends Error {
    constructor(
      readonly status: number,
      readonly code: string,
      message: string,
    ) {
      super(message);
    }
  },
  liveAnalysis: liveAnalysisMock,
}));

const { POST } = await import('@/app/api/analyze/route');

afterEach(() => {
  liveAnalysisMock.mockReset();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

const request = (cookie?: string) => new Request('http://web/api/analyze', {
  method: 'POST',
  headers: {
    'content-type': 'application/json',
    ...(cookie ? { cookie } : {}),
  },
  body: JSON.stringify({ repo: 'team/app', sha: 'A'.repeat(40) }),
});

describe('POST /api/analyze', () => {
  it('loads the commit through the control plane and passes it to live analysis', async () => {
    vi.stubEnv('BACKEND_ORIGIN', 'http://api:8000');
    const commit = {
      sha: 'a'.repeat(40),
      html_url: 'https://github.com/team/app/commit/example',
      commit: { message: 'fix: example', author: { name: 'Alice', date: '2026-10-17T01:00:00Z' } },
      author: { login: 'alice' },
      stats: { additions: 2, deletions: 1 },
      files: [{ filename: 'src/main.py', status: 'modified', additions: 2, deletions: 1, patch: '+new' }],
    };
    const result = { commit: { sha: commit.sha } };
    const fetchMock = vi.fn().mockResolvedValue(Response.json(commit));
    vi.stubGlobal('fetch', fetchMock);
    liveAnalysisMock.mockResolvedValue(result);

    const response = await POST(request('session=secret'));

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual(result);
    expect(fetchMock).toHaveBeenCalledWith(
      `http://api:8000/api/v1/github/commit?repo=team%2Fapp&sha=${'a'.repeat(40)}`,
      expect.objectContaining({
        headers: { cookie: 'session=secret', accept: 'application/json' },
        cache: 'no-store',
        signal: expect.any(AbortSignal),
      }),
    );
    expect(liveAnalysisMock).toHaveBeenCalledWith('team/app', 'a'.repeat(40), commit);
  });

  it.each([
    [403, 'FORBIDDEN', 'This repository is not reachable through your GitHub App installation.'],
    [404, 'NOT_FOUND', 'GitHub could not find this commit in team/app.'],
  ])('passes backend %s errors through unchanged', async (status, code, message) => {
    vi.stubEnv('BACKEND_ORIGIN', 'http://api:8000');
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(Response.json({ error: { code, message } }, { status })),
    );

    const response = await POST(request('session=secret'));

    expect(response.status).toBe(status);
    expect(await response.json()).toEqual({ error: { code, message } });
    expect(liveAnalysisMock).not.toHaveBeenCalled();
  });

  it('requires a session cookie before contacting the control plane', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    const response = await POST(request());

    expect(response.status).toBe(401);
    expect((await response.json()).error.code).toBe('UNAUTHENTICATED');
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
