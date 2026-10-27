import { cleanup, render, screen } from '@testing-library/react';
import type { Project, ProjectSettings, Repository } from '@hackatl/frontend-transport';
import { afterEach, expect, it, vi } from 'vitest';
import SettingsPage from '@/app/(console)/projects/[projectId]/settings/page';

const mocks = vi.hoisted(() => ({ useProject: vi.fn() }));
vi.mock('@/components/project', () => ({ useProject: mocks.useProject }));
vi.mock('@/components/repositories', () => ({
  Repositories: ({ repos }: { repos: Repository[] }) => (
    <div data-testid="selected-repositories">{repos.map(repo => <span key={repo.id}>{repo.full_name}</span>)}</div>
  ),
}));

const settings: ProjectSettings = {
  default_budget: { max_tokens: 400_000, max_usd: 10, max_wall_clock_s: 1800 },
  monitoring_policy: {
    enabled: false,
    min_interval_s: 600,
    ignore_paths_only: [],
    monitoring_budget: { max_tokens: 150_000, max_usd: 3, max_wall_clock_s: 900 },
  },
  review: {
    review_pushes: false, review_pull_requests: false, review_draft_prs: false,
    include_branches: [], exclude_branches: [], include_authors: [], exclude_authors: [],
    strictness: 2, comment_on_pull_requests: false, max_reviews_per_hour: null,
  },
  languages: ['python'],
  delivery_mode: 'manual',
  delivery_authorized_by: null,
};
const project: Project = {
  id: 'project-1',
  org_id: 'org-1',
  name: 'Payments',
  settings,
  created_at: '2026-10-23T00:00:00Z',
};
const repos = [
  { id: 'repo-1', project_id: project.id, full_name: 'acme/other', default_branch: 'main', installation_id: null, created_at: '2026-10-23T00:00:00Z' },
  { id: 'repo-2', project_id: project.id, full_name: 'acme/payments-lite', default_branch: 'main', installation_id: null, created_at: '2026-10-23T00:00:00Z' },
] as Repository[];

afterEach(cleanup);

it('manages every repository in the project from Settings', () => {
  mocks.useProject.mockReturnValue({ project, repos, selectedRepo: repos[1], reloadProject: vi.fn() });
  render(<SettingsPage />);

  expect(screen.getByTestId('selected-repositories').textContent).toBe('acme/otheracme/payments-lite');
  expect(screen.getByText(/Changes below apply to all repositories in this project/)).toBeTruthy();
});
