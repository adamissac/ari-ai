import { expect, it, vi } from 'vitest';
const calls = vi.hoisted(() => ({ projects: vi.fn(), repositories: vi.fn() }));
vi.mock('@/lib/api', () => ({ api: () => calls }));
import { projectForRepository } from '@/lib/github-connect';
it('uses the repository owner project rather than the matching organization name', async () => {
  calls.projects.mockResolvedValue({ items: [{ id: 'shared', name: 'acme' }, { id: 'actual', name: 'My application' }], next_cursor: null });
  calls.repositories.mockImplementation(async (id: string) => ({ items: id === 'actual' ? [{ id: 'repo_selected' }] : [{ id: 'repo_other' }], next_cursor: null }));
  expect(await projectForRepository('repo_selected')).toBe('actual');
  await expect(projectForRepository('missing')).rejects.toThrow('not connected');
});
