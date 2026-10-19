import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import ConnectOrgsPage from '@/app/(console)/connect/page';
import { RepoPicker } from '@/components/repo-picker';

const mocks = vi.hoisted(() => ({ useResource: vi.fn() }));
vi.mock('@/lib/use-resource', () => ({ useResource: mocks.useResource }));
vi.mock('@/components/session', () => ({
  useSession: () => ({ me: { user: { github_login: 'alice' } } }),
}));

beforeEach(() => {
  mocks.useResource.mockReturnValue({
    status: 'ready',
    data: { items: [], install_url: null, next_cursor: null },
    reload: vi.fn(),
  });
});
afterEach(cleanup);

it.each([
  ['connect page', () => render(<ConnectOrgsPage />)],
  ['repo picker', () => render(<RepoPicker projectId="prj_test" onConnected={() => {}} />)],
])('links organization repository refresh from the %s to GitHub sign-in', (_surface, renderSurface) => {
  renderSurface();
  expect(screen.getByRole('link', { name: 'Refresh from GitHub' }).getAttribute('href')).toBe(
    '/api/v1/auth/github/login',
  );
});
