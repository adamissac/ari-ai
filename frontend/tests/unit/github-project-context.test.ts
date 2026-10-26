import { expect, it, vi } from 'vitest';
const calls = vi.hoisted(() => ({ projects: vi.fn(), repositories: vi.fn(), reconnectRepository: vi.fn(), connectRepository: vi.fn() }));
vi.mock('@/lib/api', () => ({ api: () => calls }));
import { connectRepo, projectForRepository } from '@/lib/github-connect';
it('uses the repository owner project rather than the matching organization name', async () => {
  calls.projects.mockResolvedValue({ items: [{ id: 'shared', name: 'acme' }, { id: 'actual', name: 'My application' }], next_cursor: null });
  calls.repositories.mockImplementation(async (id: string) => ({ items: id === 'actual' ? [{ id: 'repo_selected' }] : [{ id: 'repo_other' }], next_cursor: null }));
  expect(await projectForRepository('repo_selected')).toBe('actual');
  await expect(projectForRepository('missing')).rejects.toThrow('not connected');
});

it('skips an unrelated failed project and stops after the repository owner', async () => {
  calls.repositories.mockClear();
  calls.projects.mockResolvedValue({ items: [{ id: 'broken' }, { id: 'actual' }, { id: 'unneeded' }] });
  calls.repositories.mockImplementation(async (id: string) => {
    if (id === 'broken') throw new Error('unrelated unavailable');
    return { items: [{ id: 'repo_selected' }] };
  });
  expect(await projectForRepository('repo_selected')).toBe('actual');
  expect(calls.repositories.mock.calls.map(call => call[0])).toEqual(['broken', 'actual']);
});

it('reconnects a disconnected repository instead of reusing its stale id', async () => {
  const repo = { full_name: 'acme/shop', installation_id: 1, default_branch: 'main', private: true, connected_repo_id: 'repo_parked', disconnected: true };
  calls.reconnectRepository.mockResolvedValue({ id: 'repo_parked', disconnected: false });
  expect(await connectRepo('acme', repo)).toBe('repo_parked');
  expect(calls.reconnectRepository).toHaveBeenCalledWith('repo_parked');
  expect(calls.connectRepository).not.toHaveBeenCalled();
  calls.reconnectRepository.mockClear();
  expect(await connectRepo('acme', { ...repo, disconnected: false })).toBe('repo_parked');
  expect(calls.reconnectRepository).not.toHaveBeenCalled();
});
