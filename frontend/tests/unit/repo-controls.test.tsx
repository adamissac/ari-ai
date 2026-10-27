import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import type { Repository } from '@hackatl/frontend-transport';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { Repositories } from '@/components/repositories';

const mocks = vi.hoisted(() => ({ updateRepository: vi.fn(), disconnectRepository: vi.fn(), reloadRepos: vi.fn() }));
vi.mock('@/lib/api', async importOriginal => ({
  ...await importOriginal<typeof import('@/lib/api')>(),
  api: () => ({ updateRepository: mocks.updateRepository, disconnectRepository: mocks.disconnectRepository }),
}));
vi.mock('@/components/project', () => ({
  useProject: () => ({ project: { id: 'prj_1' }, reloadRepos: mocks.reloadRepos, selectedRepo: null }),
}));
vi.mock('@/components/repo-picker', () => ({ RepoPicker: () => null }));
vi.mock('@/components/repo-commits', () => ({ RepoCommits: () => null }));
vi.mock('@/components/automation-status', () => ({ AutomationStatus: () => null }));

const repo = (overrides: Partial<Repository> = {}) => ({
  id: 'rep_12345678', project_id: 'prj_1', full_name: 'acme/shop', default_branch: 'main',
  installation_id: 7, automatic_assessments: false, disconnected: false, disconnected_at: null, ...overrides,
}) as unknown as Repository;

beforeEach(() => { mocks.updateRepository.mockReset().mockResolvedValue({}); mocks.disconnectRepository.mockReset().mockResolvedValue({}); mocks.reloadRepos.mockReset(); });
afterEach(cleanup);

it('lists every repository with its own automatic-reviews switch', async () => {
  render(<Repositories repos={[repo(), repo({ id: 'rep_87654321', full_name: 'acme/api', automatic_assessments: true })]} />);
  const shop = screen.getByRole('switch', { name: 'Automatic reviews for acme/shop' });
  expect(shop.getAttribute('aria-checked')).toBe('false');
  expect(screen.getByRole('switch', { name: 'Automatic reviews for acme/api' }).getAttribute('aria-checked')).toBe('true');
  fireEvent.click(shop);
  await vi.waitFor(() => expect(mocks.reloadRepos).toHaveBeenCalled());
  expect(mocks.updateRepository).toHaveBeenCalledWith('rep_12345678', { automatic_assessments: true });
});

it('disconnects only after a confirmation', async () => {
  render(<Repositories repos={[repo()]} />);
  fireEvent.click(screen.getByRole('button', { name: 'Disconnect…' }));
  expect(mocks.disconnectRepository).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Disconnect' }));
  await vi.waitFor(() => expect(mocks.disconnectRepository).toHaveBeenCalledWith('rep_12345678'));
});
