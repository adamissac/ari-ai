import type { MeResponse } from '@hackatl/frontend-transport';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';

const session = vi.fn();
const logout = vi.fn();
vi.mock('next/navigation', () => ({ usePathname: () => '/projects' }));
vi.mock('@/lib/api', () => ({ api: () => ({ session, logout }) }));
import { notifySessionChanged } from '@/lib/session-events';
import { AccountLink } from '@/components/account-link';

const signedIn: MeResponse = {
  user: { id: 'usr_12345678', github_login: 'octo-cat', display_name: null, created_at: '2026-10-17T00:00:00Z' },
  memberships: [{ organization: { id: 'org_12345678', name: 'Octo Org', created_at: '2026-10-17T00:00:00Z' }, role: 'owner' }],
  csrf_token: 'csrf-token',
};

afterEach(() => { cleanup(); session.mockReset(); logout.mockReset(); });

it('shows "Sign in" (to the console sign-in) when signed out or the backend is unreachable', async () => {
  session.mockRejectedValue(new Error('401'));
  render(<AccountLink />);
  const link = await screen.findByTestId('header-signin');
  expect(link.textContent).toContain('Sign in');
  expect(link.getAttribute('href')).toBe('/projects');
});

it('shows the signed-in login instead, linking to projects', async () => {
  session.mockResolvedValue(signedIn);
  render(<AccountLink />);
  const button = await screen.findByTestId('header-account');
  expect(button.textContent).toContain('octo-cat');
  expect(button.getAttribute('aria-haspopup')).toBe('menu');
  expect(button.getAttribute('aria-expanded')).toBe('false');
  expect(screen.getByTestId('signed-in-user').textContent).toBe('octo-cat');
  expect(screen.queryByRole('menu')).toBeNull();
  expect(screen.queryByTestId('header-signin')).toBeNull();
});

it('applies session-change payloads without refetching the session', async () => {
  session.mockResolvedValue({ ...signedIn, user: { ...signedIn.user, github_login: 'initial-cat' } });
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

it('opens on ArrowDown, focuses the first item, and closes on Escape with focus restored', async () => {
  session.mockResolvedValue(signedIn);
  render(<AccountLink />);
  const button = await screen.findByTestId('header-account');
  fireEvent.keyDown(button, { key: 'ArrowDown' });
  const menu = await screen.findByRole('menu');
  const projects = screen.getByRole('menuitem', { name: 'Projects' });
  expect(menu.textContent).toContain('Signed in as octo-cat');
  expect(menu.textContent).toContain('Octo Org · owner');
  await waitFor(() => expect(document.activeElement).toBe(projects));
  fireEvent.keyDown(projects, { key: 'Escape' });
  await waitFor(() => expect(screen.queryByRole('menu')).toBeNull());
  expect(document.activeElement).toBe(button);

  fireEvent.keyDown(button, { key: 'Enter' });
  const reopenedProjects = await screen.findByRole('menuitem', { name: 'Projects' });
  await waitFor(() => expect(document.activeElement).toBe(reopenedProjects));
  fireEvent.keyDown(reopenedProjects, { key: 'Escape' });
  fireEvent.keyDown(button, { key: ' ' });
  await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('menuitem', { name: 'Projects' })));
});

it('closes on outside click and moves focus out when Tab is pressed', async () => {
  session.mockResolvedValue(signedIn);
  render(<><AccountLink /><button type="button">After account</button></>);
  const button = await screen.findByTestId('header-account');
  fireEvent.click(button);
  await screen.findByRole('menu');
  const signOut = screen.getByRole('menuitem', { name: 'Sign out' });
  fireEvent.keyDown(signOut, { key: 'Tab' });
  await waitFor(() => expect(screen.queryByRole('menu')).toBeNull());
  expect(document.activeElement).toBe(screen.getByRole('button', { name: 'After account' }));

  fireEvent.click(button);
  await screen.findByRole('menu');
  fireEvent.pointerDown(document.body);
  await waitFor(() => expect(screen.queryByRole('menu')).toBeNull());
});

it('keeps the menu open and shows the specified message when sign out fails', async () => {
  session.mockResolvedValue(signedIn);
  logout.mockRejectedValueOnce(new Error('offline'));
  render(<AccountLink />);
  const button = await screen.findByTestId('header-account');
  fireEvent.click(button);
  await screen.findByRole('menu');
  fireEvent.click(screen.getByRole('menuitem', { name: 'Sign out' }));
  expect((await screen.findByRole('alert')).textContent).toBe('Sign out failed; you are still signed in');
  expect(screen.getByRole('menu')).toBeTruthy();
});
