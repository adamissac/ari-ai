import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

const signOut = vi.fn();
vi.mock('@/components/session', () => ({
  useSession: () => ({
    me: { user: { id: 'usr_12345678', github_login: 'tester', display_name: null, created_at: '2026-10-17T00:00:00Z' }, memberships: [], csrf_token: 'x' },
    refresh: () => undefined,
    signOut,
  }),
}));

import { UserBar } from '@/components/user-bar';

afterEach(() => { cleanup(); signOut.mockReset(); });

describe('UserBar sign out', () => {
  it('shows an explicit error and keeps the user signed in when logout fails', async () => {
    signOut.mockRejectedValueOnce(new TypeError('Failed to fetch'));
    render(<UserBar />);
    fireEvent.click(screen.getByRole('button', { name: /sign out/i }));
    await waitFor(() => expect(screen.getByTestId('error-state').textContent).toContain('you are still signed in'));
    expect(screen.getByTestId('signed-in-user').textContent).toBe('tester');
    expect((screen.getByRole('button', { name: /sign out/i }) as HTMLButtonElement).disabled).toBe(false);
  });
  it('calls signOut once per click', async () => {
    signOut.mockResolvedValueOnce(undefined);
    render(<UserBar />);
    fireEvent.click(screen.getByRole('button', { name: /sign out/i }));
    await waitFor(() => expect(signOut).toHaveBeenCalledTimes(1));
  });
});
