import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { Project, Repository } from '@hackatl/frontend-transport';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import SetupPage from '@/app/(console)/projects/[projectId]/setup/page';
import { progressToServer, setupProgressKey, type SetupProgress } from '@/lib/setup-progress';

function serverSetup(progress: SetupProgress) {
  return { repo_id: 'rep_12345678', ...progressToServer(progress), completed_at: null, updated_at: null };
}

const mocks = vi.hoisted(() => ({
  query: 'repo=rep_12345678',
  useResource: vi.fn(),
  project: null as unknown,
  reloadProject: vi.fn(),
  server: null as unknown,
  saveRepositorySetup: vi.fn(),
  updateRepository: vi.fn(),
  updateProject: vi.fn(),
}));
vi.mock('@/lib/api', async importOriginal => ({
  ...await importOriginal<typeof import('@/lib/api')>(),
  api: () => ({ saveRepositorySetup: mocks.saveRepositorySetup, updateRepository: mocks.updateRepository, updateProject: mocks.updateProject }),
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
  mocks.server = serverSetup({ answers: {}, complete: false });
  mocks.saveRepositorySetup.mockReset();
  mocks.saveRepositorySetup.mockImplementation((_id: string, body: unknown) => Promise.resolve({ repo_id: repo.id, completed_at: null, updated_at: null, ...(body as object) }));
  mocks.useResource.mockImplementation((key: string | null) => {
    if (key?.includes('setup-progress')) return { status: 'ready', data: mocks.server, reload: vi.fn() };
    if (key?.includes('setup-repos')) return { status: 'ready', data: { items: [repo] }, reload: vi.fn() };
    if (key?.includes('setup-scopes')) return { status: 'ready', data: { items: [] }, reload: vi.fn() };
    if (key?.includes('setup-runs')) return { status: 'ready', data: { items: [] }, reload: vi.fn() };
    return { status: 'ready', data: { items: [] }, reload: vi.fn() };
  });
});
afterEach(cleanup);

it('resumes from the server copy in a browser that never saw setup', async () => {
  mocks.server = serverSetup({ answers: { readiness: true, strictness: '2' }, complete: false });
  render(<SetupPage />);
  expect(await screen.findByTestId('setup-step-3')).toBeTruthy();
  expect(screen.getByRole('progressbar', { name: 'Question 3 of 8' })).toBeTruthy();
  expect(screen.getAllByText('SAVED')).toHaveLength(2);
  expect(mocks.saveRepositorySetup).not.toHaveBeenCalled();
});

it('moves browser-only progress from an earlier build to the server', async () => {
  localStorage.setItem(setupProgressKey(project.id, repo.id), JSON.stringify({ answers: { readiness: true }, complete: false }));
  render(<SetupPage />);
  expect(await screen.findByTestId('setup-step-2')).toBeTruthy();
  await waitFor(() => expect(mocks.saveRepositorySetup).toHaveBeenCalledTimes(1));
  expect(mocks.saveRepositorySetup.mock.calls[0]![1].answers.readiness).toBe(true);
  await waitFor(() => expect(localStorage.getItem(setupProgressKey(project.id, repo.id))).toBeNull());
});

it('ignores stale browser progress once the server has saved setup', async () => {
  mocks.server = serverSetup({ answers: { readiness: true, strictness: '2', reviewChanges: true }, complete: false });
  localStorage.setItem(setupProgressKey(project.id, repo.id), JSON.stringify({ answers: { readiness: true }, complete: false }));
  render(<SetupPage />);
  expect(await screen.findByTestId('setup-step-4')).toBeTruthy();
  expect(mocks.saveRepositorySetup).not.toHaveBeenCalled();
});

it('shows a save failure and stays on the question', async () => {
  mocks.saveRepositorySetup.mockRejectedValueOnce(new Error('offline'));
  render(<SetupPage />);
  fireEvent.click(await screen.findByRole('button', { name: /^Continue$/ }));
  expect(await screen.findByText(/offline/)).toBeTruthy();
  expect(screen.getByTestId('setup-step-1')).toBeTruthy();
});

it('does not run setup for a disconnected repository', async () => {
  mocks.useResource.mockImplementation((key: string | null) => {
    if (key?.includes('setup-repos')) return { status: 'ready', data: { items: [{ ...repo, disconnected: true }] }, reload: vi.fn() };
    return { status: 'ready', data: { items: [] }, reload: vi.fn() };
  });
  render(<SetupPage />);
  expect(await screen.findByTestId('setup-disconnected')).toBeTruthy();
  expect(screen.queryByTestId('setup-step-1')).toBeNull();
});

it('does not let a URL question parameter skip ahead', async () => {
  mocks.server = serverSetup({ answers: { readiness: true }, complete: false });
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
  expect(mocks.saveRepositorySetup).toHaveBeenCalledWith(repo.id, expect.objectContaining({ complete: false }));
  expect(mocks.saveRepositorySetup.mock.calls[0]![1].answers.readiness).toBe(true);
  expect(localStorage.getItem(setupProgressKey(project.id, repo.id))).toBeNull();
});

it('links saved reviews to the Commits assessment history', async () => {
  mocks.server = serverSetup({
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
  });
  mocks.useResource.mockImplementation((key: string | null) => {
    if (key?.includes('setup-progress')) return { status: 'ready', data: mocks.server, reload: vi.fn() };
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

const ALL_ANSWERS = {
  readiness: true,
  strictness: '2',
  reviewChanges: true,
  comments: false,
  watch: false,
  scope: true,
  delivery: 'pull_request',
} as const;

it('shows finished setup as complete instead of asking the questions again', async () => {
  mocks.server = { ...serverSetup({ answers: { ...ALL_ANSWERS, reviewStart: true }, complete: true }), completed_at: '2026-10-26T12:00:00Z' };
  render(<SetupPage />);
  expect(await screen.findByTestId('setup-done')).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'Finish setup' })).toBeNull();
  expect(screen.queryByTestId('setup-step-8')).toBeNull();
  expect(screen.getByRole('link', { name: 'Go to Analytics' }).getAttribute('href')).toBe(`/projects/${project.id}?repo=${repo.id}`);
  fireEvent.click(screen.getByRole('button', { name: 'Back to setup' }));
  expect(screen.queryByTestId('setup-done')).toBeNull();
});

it('leaves the walkthrough once setup is finished', async () => {
  localStorage.setItem(`ari-tour:${project.id}`, 'complete');
  mocks.server = serverSetup({ answers: ALL_ANSWERS, complete: false });
  render(<SetupPage />);
  expect(await screen.findByTestId('setup-step-8')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Finish setup' }));
  expect(await screen.findByTestId('setup-done')).toBeTruthy();
  expect(mocks.saveRepositorySetup).toHaveBeenCalledWith(repo.id, expect.objectContaining({ complete: true }));
});

it('does not offer direct commits to the default branch', async () => {
  mocks.server = serverSetup({ answers: { readiness: true, strictness: '2', reviewChanges: true, comments: false, watch: false, scope: true }, complete: false });
  render(<SetupPage />);
  expect(await screen.findByTestId('setup-step-7')).toBeTruthy();
  expect(screen.getByText('Open a pull request')).toBeTruthy();
  expect(screen.queryByText('Commit to the default branch')).toBeNull();
});

it('turns on automatic reviews for this repository when the owner says to watch it', async () => {
  mocks.updateProject.mockResolvedValue(project);
  mocks.updateRepository.mockResolvedValue({ ...repo, automatic_assessments: true });
  mocks.server = serverSetup({ answers: { readiness: true, strictness: '2', reviewChanges: true, comments: false }, complete: false });
  render(<SetupPage />);
  expect(await screen.findByTestId('setup-step-5')).toBeTruthy();
  fireEvent.click(screen.getByLabelText('Yes, watch for commits'));
  fireEvent.click(screen.getByRole('button', { name: /^Continue$/ }));
  expect(await screen.findByTestId('setup-step-6')).toBeTruthy();
  expect(mocks.updateRepository).toHaveBeenCalledWith(repo.id, { automatic_assessments: true });
});
