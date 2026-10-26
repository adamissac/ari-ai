import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { RepoPicker } from '@/components/repo-picker';

const mocks = vi.hoisted(() => ({ useResource: vi.fn(), reconnectRepository: vi.fn(), projectForRepository: vi.fn() }));
vi.mock('@/lib/use-resource', () => ({ useResource: mocks.useResource }));
vi.mock('@/lib/api', async importOriginal => ({
  ...await importOriginal<typeof import('@/lib/api')>(),
  api: () => ({ reconnectRepository: mocks.reconnectRepository, connectRepository: vi.fn() }),
}));
vi.mock('@/lib/github-connect', () => ({ projectForRepository: mocks.projectForRepository }));
vi.mock('@/components/refresh-from-github', () => ({ RefreshFromGitHub: () => null }));

beforeEach(() => {
  mocks.reconnectRepository.mockReset().mockResolvedValue({ id: 'rep_parked', disconnected: false });
  mocks.useResource.mockReturnValue({ status: 'ready', reload: vi.fn(), data: { install_url: null, live_checked: true, items: [
    { full_name: 'acme/parked', installation_id: 1, default_branch: 'main', private: false, connected_repo_id: 'rep_parked', disconnected: true },
  ] } });
});
afterEach(cleanup);

it('reconnects a disconnected repository that belongs to this project', async () => {
  mocks.projectForRepository.mockResolvedValue('prj_here');
  const onConnected = vi.fn();
  render(<RepoPicker projectId="prj_here" onConnected={onConnected} />);
  fireEvent.click(screen.getByRole('button', { name: 'Reconnect acme/parked' }));
  await vi.waitFor(() => expect(onConnected).toHaveBeenCalled());
  expect(mocks.reconnectRepository).toHaveBeenCalledWith('rep_parked');
});

it("refuses to re-enable another project's repository from this picker", async () => {
  mocks.projectForRepository.mockResolvedValue('prj_other');
  render(<RepoPicker projectId="prj_here" onConnected={vi.fn()} />);
  fireEvent.click(screen.getByRole('button', { name: 'Reconnect acme/parked' }));
  expect(await screen.findByText(/belongs to another project/)).toBeTruthy();
  expect(mocks.reconnectRepository).not.toHaveBeenCalled();
});
