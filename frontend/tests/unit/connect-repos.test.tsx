import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import ConnectReposPage from '@/app/(console)/connect/[org]/page';

const mocks = vi.hoisted(() => ({ useResource: vi.fn(), push: vi.fn() }));
vi.mock('@/lib/use-resource', () => ({ useResource: mocks.useResource }));
vi.mock('next/navigation', () => ({
  useParams: () => ({ org: 'acme' }),
  useRouter: () => ({ push: mocks.push }),
}));
vi.mock('@/lib/github-connect', () => ({
  connectRepo: vi.fn(),
  projectForRepository: vi.fn(),
}));

const longName = 'acme/a-repository-name-that-is-long-enough-to-require-a-title-attribute';

beforeEach(() => {
  mocks.useResource.mockReturnValue({
    status: 'ready',
    data: { items: [
      { full_name: longName, installation_id: 1, default_branch: 'trunk', private: false, connected_repo_id: null, disconnected: false },
      { full_name: 'acme/payments-lite', installation_id: 1, default_branch: 'main', private: true, connected_repo_id: 'rep_12345678', disconnected: false },
      { full_name: 'acme/parked', installation_id: 1, default_branch: 'main', private: false, connected_repo_id: 'rep_87654321', disconnected: true },
    ], install_url: null },
    reload: vi.fn(),
  });
});
afterEach(cleanup);

it('filters full repository names case-insensitively and titles long names', () => {
  render(<ConnectReposPage />);
  const longRow = screen.getByTestId(`connect-repo-${longName}`);
  expect(longRow.querySelector('[title]')?.getAttribute('title')).toBe(longName);
  expect(screen.getAllByText('public')).toHaveLength(2);
  expect(screen.getByText('private')).toBeTruthy();
  expect(screen.getByText('Connected')).toBeTruthy();
  expect(screen.getByText('Continue setup')).toBeTruthy();
  // A disconnected repository is never shown as connected.
  const parked = screen.getByTestId('connect-repo-acme/parked');
  expect(parked.textContent).toContain('Disconnected');
  expect(parked.textContent).toContain('Reconnect');
  expect(parked.textContent).not.toContain('Continue setup');

  fireEvent.change(screen.getByLabelText('Filter repositories'), { target: { value: 'PAYMENTS' } });
  expect(screen.getByTestId('connect-repo-acme/payments-lite')).toBeTruthy();
  expect(screen.queryByTestId(`connect-repo-${longName}`)).toBeNull();
  fireEvent.change(screen.getByLabelText('Filter repositories'), { target: { value: 'no-match' } });
  expect(screen.getByText('No repositories match "no-match"')).toBeTruthy();
});
