import { expect, it, vi } from 'vitest';
const calls = vi.hoisted(() => ({ projects: vi.fn(), repositories: vi.fn(), repository: vi.fn(), githubRepositories: vi.fn(), reconnectRepository: vi.fn(), connectRepository: vi.fn(), session: vi.fn() }));
vi.mock('@/lib/api', () => ({ api: () => calls }));
import { connectRepo, projectFor, projectForRepository } from '@/lib/github-connect';
it('reads the repository owner project from the API, not from project names', async () => {
  calls.repository.mockImplementation(async (id: string) => {
    if (id !== 'repo_selected') throw new Error('not found');
    return { id, project_id: 'actual' };
  });
  expect(await projectForRepository('repo_selected')).toBe('actual');
  await expect(projectForRepository('missing')).rejects.toThrow('not found');
  expect(calls.projects).not.toHaveBeenCalled();
});

it('joins the project of a sibling repository even after that project was renamed', async () => {
  calls.session.mockResolvedValue({ memberships: [{ role: 'owner', organization: { id: 'org_mine' } }, { role: 'viewer', organization: { id: 'org_theirs' } }] });
  calls.githubRepositories.mockResolvedValue({ items: [{ full_name: 'Acme/web', connected_repo_id: 'repo_web', disconnected: false }], install_url: null });
  calls.repository.mockResolvedValue({ id: 'repo_web', project_id: 'renamed_project' });
  calls.projects.mockResolvedValue({ items: [{ id: 'renamed_project', name: 'Payments', org_id: 'org_mine' }, { id: 'name_match', name: 'acme', org_id: 'org_mine' }] });
  expect(await projectFor('acme')).toBe('renamed_project');
  calls.githubRepositories.mockResolvedValue({ items: [], install_url: null });
  expect(await projectFor('acme')).toBe('name_match');
});

it('never picks a project the user cannot connect repositories to', async () => {
  calls.session.mockResolvedValue({ memberships: [{ role: 'owner', organization: { id: 'org_mine' } }, { role: 'viewer', organization: { id: 'org_theirs' } }] });
  calls.githubRepositories.mockResolvedValue({ items: [{ full_name: 'acme/web', connected_repo_id: 'repo_web', disconnected: false }], install_url: null });
  calls.repository.mockResolvedValue({ id: 'repo_web', project_id: 'read_only' });
  calls.projects.mockResolvedValue({ items: [{ id: 'read_only', name: 'acme', org_id: 'org_theirs' }, { id: 'mine', name: 'acme', org_id: 'org_mine' }] });
  expect(await projectFor('acme')).toBe('mine');
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
