import type { MeResponse } from '@hackatl/frontend-transport';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';

const session = vi.fn();
vi.mock('next/navigation', () => ({ usePathname: () => '/pricing' }));
vi.mock('@/lib/api', () => ({ api: () => ({ session }) }));
import { notifySessionChanged } from '@/lib/session-events';
import { AccountLink } from '@/components/account-link';

afterEach(() => { cleanup(); session.mockReset(); });

it('shows "Sign in" (to the console sign-in) when signed out or the backend is unreachable', async () => {
  session.mockRejectedValue(new Error('401'));
  render(<AccountLink />);
  const link = await screen.findByTestId('header-signin');
  expect(link.textContent).toContain('Sign in');
  expect(link.getAttribute('href')).toBe('/projects');
});

it('shows the signed-in login instead, linking to projects', async () => {
  session.mockResolvedValue({ user: { github_login: 'octo-cat' } });
  render(<AccountLink />);
  await waitFor(() => expect(screen.getByTestId('header-account').textContent).toContain('octo-cat'));
  expect(screen.getByTestId('header-account').getAttribute('href')).toBe('/projects');
  expect(screen.queryByTestId('header-signin')).toBeNull();
});

it('applies session-change payloads without refetching the session', async () => {
  session.mockResolvedValue({ user: { github_login: 'initial-cat' } });
  render(<AccountLink />);
  await waitFor(() => expect(screen.getByTestId('header-account').textContent).toContain('initial-cat'));

  await act(async () => {
    notifySessionChanged({
      user: {
        id: 'usr_12345678',
        github_login: 'octo-cat',
        display_name: null,
        created_at: '2026-10-17T00:00:00Z',
      },
      memberships: [],
      csrf_token: 'csrf-token',
    } satisfies MeResponse);
  });
  await waitFor(() => expect(screen.getByTestId('header-account').textContent).toContain('octo-cat'));

  await act(async () => { notifySessionChanged(null); });
  await waitFor(() => expect(screen.queryByTestId('header-account')).toBeNull());
  expect(screen.getByTestId('header-signin').textContent).toContain('Sign in');
  expect(session).toHaveBeenCalledTimes(1);
});
