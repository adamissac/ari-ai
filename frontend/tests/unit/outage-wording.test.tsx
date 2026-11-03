import { ApiClient, ApiError } from '@hackatl/frontend-transport';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('server-only', () => ({}));
const { proxy } = await import('@/lib/backend-proxy');
import { ErrorState } from '@/components/ui';
import { describeError } from '@/lib/api';

afterEach(() => { cleanup(); vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

const apiError = (status: number, code: ConstructorParameters<typeof ApiError>[1]['code'], message: string, details: Record<string, unknown> = {}) =>
  new ApiError(status, { code, message, details, request_id: details.origin ? null : 'req_1' });

/** Run a browser request through the real proxy and the real transport client, with `upstream` as the backend. */
async function throughProxy(upstream: () => Promise<Response>): Promise<unknown> {
  vi.stubEnv('BACKEND_ORIGIN', 'http://api:8000');
  const client = new ApiClient({
    baseUrl: 'http://web/api/v1',
    fetch: (async (input: RequestInfo | URL, init?: RequestInit) => {
      vi.stubGlobal('fetch', vi.fn(upstream));
      return proxy(new Request(input, init));
    }) as typeof fetch,
  });
  return client.session().then(() => { throw new Error('expected a failure'); }, (error: unknown) => error);
}

describe('a backend outage is not presented as a GitHub problem', () => {
  it.each([
    ['no running deployment (Railway fallback 404)', () => Promise.resolve(Response.json({ status: 'error', code: 404, message: 'Application not found' }, { status: 404, headers: { 'x-railway-fallback': 'true' } }))],
    ['gateway page during a deploy', () => Promise.resolve(Response.json({ status: 'error', code: 502, message: 'Application failed to respond' }, { status: 502 }))],
    ['connection refused', () => Promise.reject(new TypeError('connect ECONNREFUSED'))],
  ])('%s → "Ari is unavailable", no GitHub App advice', async (_name, upstream) => {
    const error = await throughProxy(upstream);
    expect(error).toBeInstanceOf(ApiError);
    const e = describeError(error);
    expect(e.title).toBe('Ari is unavailable');
    expect(e.detail).toMatch(/Nothing was started, and no repository was read or changed/);
    expect(e.recovery).toMatch(/not a problem with your GitHub connection/);
    expect(e.recovery).not.toMatch(/GitHub App/);
  });

  it('an API-raised GitHub failure still points at the GitHub App', () => {
    const e = describeError(apiError(503, 'SUBSYSTEM_UNAVAILABLE', 'GitHub did not return commits'));
    expect(e.title).toBe('Request failed (503)');
    expect(e.recovery).toMatch(/Ari GitHub App/);
  });

  it('an API-raised non-GitHub failure does not mention GitHub', () => {
    const e = describeError(apiError(503, 'SUBSYSTEM_UNAVAILABLE', 'Indexer version is unavailable'));
    expect(e.recovery).toMatch(/nothing was started/);
    expect(e.recovery).not.toMatch(/GitHub/);
  });

  it('origin=proxy on any other code is not treated as an outage', () => {
    expect(describeError(apiError(404, 'NOT_FOUND', 'not found', { origin: 'proxy' })).title).toBe('Not found');
  });
});

describe('an expired session offers sign-in, not a retry loop', () => {
  it.each([[401, 'UNAUTHENTICATED'], [403, 'CSRF_FAILED']] as const)('%i %s', (status, code) => {
    render(<ErrorState error={apiError(status, code, 'session expired')} onRetry={() => {}} />);
    expect(screen.getByTestId('sign-in-again').getAttribute('href')).toBe('/connect');
    expect(screen.queryByRole('button', { name: 'Retry' })).toBeNull();
  });

  it('other errors keep Retry and no sign-in link', () => {
    render(<ErrorState error={apiError(500, 'INTERNAL', 'boom')} onRetry={() => {}} />);
    expect(screen.getByRole('button', { name: 'Retry' })).toBeTruthy();
    expect(screen.queryByTestId('sign-in-again')).toBeNull();
  });
});
