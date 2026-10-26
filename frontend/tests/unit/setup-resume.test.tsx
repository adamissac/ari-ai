import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import type { Project, Repository } from '@hackatl/frontend-transport';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import SetupPage from '@/app/(console)/projects/[projectId]/setup/page';
import { setupProgressKey } from '@/lib/setup-progress';

const mocks = vi.hoisted(() => ({
  query: 'repo=rep_12345678',
  useResource: vi.fn(),
  project: null as unknown,
  reloadProject: vi.fn(),
}));
vi.mock('@/components/project', () => ({ useProject: () => mocks.project }));
vi.mock('@/components/onboarding/build-recipe-readiness', () => ({ BuildRecipeReadiness: () => <p>Recipe readiness</p> }));
vi.mock('@/lib/use-resource', () => ({ useResource: mocks.useResource }));
vi.mock('next/navigation', () => ({
  useSearchParams: () => new URLSearchParams(mocks.query),
}));

const project = {
  id: 'prj_12345678',
  name: 'Payments',
  settings: {
    review: { strictness: 2, review_pushes: false, review_pull_requests: false, comment_on_pull_requests: false },
    monitoring_policy: { enabled: false },
    delivery_mode: 'pull_request',
  },
} as unknown as Project;
const repo = {
  id: 'rep_12345678',
  full_name: 'acme/payments-lite',
  default_branch: 'main',
  installation_id: null,
} as unknown as Repository;

beforeEach(() => {
  localStorage.clear();
  mocks.query = 'repo=rep_12345678';
  mocks.project = { project, reloadProject: vi.fn() };
  mocks.useResource.mockImplementation((key: string | null) => {
    if (key?.includes('setup-repos')) return { status: 'ready', data: { items: [repo] }, reload: vi.fn() };
    if (key?.includes('setup-scopes')) return { status: 'ready', data: { items: [] }, reload: vi.fn() };
    if (key?.includes('setup-runs')) return { status: 'ready', data: { items: [] }, reload: vi.fn() };
    return { status: 'ready', data: { items: [] }, reload: vi.fn() };
  });
});
afterEach(cleanup);

it('resumes from the first unanswered question and announces progress', async () => {
  localStorage.setItem(setupProgressKey(project.id, repo.id), JSON.stringify({
    answers: { readiness: true, strictness: '2' },
    complete: false,
  }));
  render(<SetupPage />);
  expect(await screen.findByTestId('setup-step-3')).toBeTruthy();
  expect(screen.getByRole('progressbar', { name: 'Question 3 of 8' })).toBeTruthy();
  expect(screen.getAllByText('SAVED')).toHaveLength(2);
});

it('does not let a URL question parameter skip ahead', async () => {
  localStorage.setItem(setupProgressKey(project.id, repo.id), JSON.stringify({ answers: { readiness: true }, complete: false }));
  mocks.query = 'repo=rep_12345678&step=8';
  render(<SetupPage />);
  expect(await screen.findByTestId('setup-step-2')).toBeTruthy();
  expect(screen.queryByTestId('setup-step-8')).toBeNull();
});

it('saves the readiness answer before advancing', async () => {
  render(<SetupPage />);
  expect(await screen.findByTestId('setup-step-1')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: /^Continue$/ }));
  expect(await screen.findByTestId('setup-step-2')).toBeTruthy();
  const stored = JSON.parse(localStorage.getItem(setupProgressKey(project.id, repo.id)) ?? '{}');
  expect(stored.answers.readiness).toBe(true);
});

it('links saved reviews to the Commits assessment history', async () => {
  localStorage.setItem(setupProgressKey(project.id, repo.id), JSON.stringify({
    answers: {
      readiness: true,
      strictness: '2',
      reviewChanges: true,
      comments: false,
      watch: false,
      scope: true,
      delivery: 'pull_request',
    },
    complete: false,
  }));
  mocks.useResource.mockImplementation((key: string | null) => {
    if (key?.includes('setup-repos')) return { status: 'ready', data: { items: [repo] }, reload: vi.fn() };
    if (key?.includes('setup-scopes')) return { status: 'ready', data: { items: [] }, reload: vi.fn() };
    if (key?.includes('setup-runs')) return { status: 'ready', data: { items: [{ repo_id: repo.id }] }, reload: vi.fn() };
    return { status: 'ready', data: { items: [] }, reload: vi.fn() };
  });
  render(<SetupPage />);
  expect(await screen.findByTestId('setup-step-8')).toBeTruthy();
  expect(screen.getByRole('link', { name: 'See your reviews' }).getAttribute('href'))
    .toBe(`/projects/${project.id}/commits?repo=${encodeURIComponent(repo.id)}#assessments`);
});
