import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ApiClient } from '@hackatl/frontend-transport';
import { setApiClient } from '@/lib/api';

vi.mock('@/lib/deployment', () => ({ DEMO_ONLY: false }));

import DefenseLabPage from '@/app/lab/page';

afterEach(() => {
  cleanup();
  setApiClient(undefined);
  vi.unstubAllGlobals();
});

it('keeps the offline Defense Lab visible without a signed-in session and hides the project panel', async () => {
  const apiFetch: typeof fetch = async () => Response.json({
    error: { code: 'UNAUTHENTICATED', message: 'Sign in required', details: {}, request_id: null },
  }, { status: 401 });
  setApiClient(new ApiClient({ baseUrl: 'http://localhost/api/v1', fetch: apiFetch }));
  const bundleFetch = vi.fn(async () => Response.json({ error: 'bundles unavailable' }, { status: 503 }));
  vi.stubGlobal('fetch', bundleFetch);

  render(<DefenseLabPage />);

  expect(screen.getByTestId('lab-intro').textContent).toBe("What your team sees while Ari's defender watches the network.");
  expect(screen.getByTestId('lab-caveat').textContent).toBe('Recorded run · test network');
  await waitFor(() => expect(bundleFetch).toHaveBeenCalled());
  expect(screen.queryByText('Your 24/7 defense')).toBeNull();
});
