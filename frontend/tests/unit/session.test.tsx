import type { MeResponse } from '@hackatl/frontend-transport';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';

const session = vi.fn();
const logout = vi.fn();
const devLogin = vi.fn();
vi.mock('next/navigation', () => ({ usePathname: () => '/projects' }));
vi.mock('@/lib/api', () => ({ api: () => ({ session, logout, devLogin }) }));

import { AccountLink } from '@/components/account-link';
import { SessionGate } from '@/components/session';
import { UserBar } from '@/components/user-bar';

const me: MeResponse = {
  user: {
    id: 'usr_12345678',
    github_login: 'octo-cat',
    display_name: null,
    created_at: '2026-10-17T00:00:00Z',
  },
  memberships: [],
  csrf_token: 'csrf-token',
};

beforeEach(() => {
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: query.includes('reduced-motion'),
    media: query,
    addEventListener() {},
    removeEventListener() {},
  }));
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  session.mockReset();
  logout.mockReset();
  devLogin.mockReset();
});

it('updates the header on SessionGate sign-out without another session read or navigation', async () => {
  session.mockResolvedValue(me);
  logout.mockResolvedValue(undefined);
  const pathname = window.location.pathname;

  render(
    <>
      <AccountLink />
      <SessionGate><UserBar /></SessionGate>
    </>,
  );

  await waitFor(() => {
    expect(screen.getByTestId('header-account').textContent).toContain('octo-cat');
    expect(screen.getByRole('button', { name: /sign out/i })).toBeTruthy();
    expect(session).toHaveBeenCalledTimes(2);
  });
  const sessionReadsBeforeLogout = session.mock.calls.length;

  fireEvent.click(screen.getByRole('button', { name: /sign out/i }));

  await waitFor(() => expect(screen.queryByTestId('header-account')).toBeNull());
  expect(screen.getByTestId('header-signin')).toBeTruthy();
  expect(logout).toHaveBeenCalledTimes(1);
  expect(session).toHaveBeenCalledTimes(sessionReadsBeforeLogout);
  expect(window.location.pathname).toBe(pathname);
});
