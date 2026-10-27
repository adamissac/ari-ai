import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import type { Repository } from '@hackatl/frontend-transport';
import { ApiError } from '@hackatl/frontend-transport';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { BuildRecipeReadiness, loadRecipeAudit } from '@/components/onboarding/build-recipe-readiness';

const mocks = vi.hoisted(() => ({ useResource: vi.fn(), auditEvents: vi.fn(), retryBuildRecipe: vi.fn() }));
vi.mock('@/lib/use-resource', () => ({ useResource: mocks.useResource }));
vi.mock('@/lib/api', () => ({ api: () => ({ auditEvents: mocks.auditEvents, retryBuildRecipe: mocks.retryBuildRecipe }) }));

const repo = (installationId: number | null = 42) => ({
  id: 'rep_12345678',
  full_name: 'acme/payments-lite',
  default_branch: 'main',
  installation_id: installationId,
}) as unknown as Repository;

const event = (action: string, details: Record<string, unknown> = {}) => ({
  action, subject_id: 'rep_12345678', at: '2026-10-17T03:00:00Z', details,
});

beforeEach(() => {
  mocks.auditEvents.mockReset();
  mocks.useResource.mockReturnValue({ status: 'ready', data: { items: [], truncated: false }, reload: vi.fn() });
});
afterEach(cleanup);

it.each([
  ['recipe.pr_opened', 'PR OPENED', 'Ari opened a pull request adding build_recipe.json'],
  ['recipe.skipped', 'SKIPPED', 'No supported build command'],
  ['recipe.unsupported', 'UNSUPPORTED', 'Language is not supported'],
  ['recipe.invalid', 'INVALID', 'missing build command'],
  ['recipe.failed', 'FAILED', 'Recipe generation failed'],
])('maps %s to its readiness status', (action, status, text) => {
  const details = action === 'recipe.invalid'
    ? { reasons: ['missing build command'] }
    : action === 'recipe.pr_opened'
      ? { url: 'https://github.com/acme/payments-lite/pull/2' }
      : { reason: text };
  mocks.useResource.mockReturnValue({ status: 'ready', data: { items: [event(action, details)] }, reload: vi.fn() });
  render(<BuildRecipeReadiness projectId="prj_12345678" repo={repo()} />);
  expect(screen.getByText(status)).toBeTruthy();
  expect(screen.getByText(new RegExp(text))).toBeTruthy();
  if (action === 'recipe.pr_opened') expect(screen.getByRole('link', { name: 'View pull request' }).getAttribute('href')).toBe(details.url);
});

it('shows no-result refresh and filters events to this repository', () => {
  mocks.useResource.mockReturnValue({
    status: 'ready',
    data: { items: [{ ...event('recipe.failed', { reason: 'other repo' }), subject_id: 'rep_otherid' }, { ...event('recipe.skipped'), subject_id: 'rep_otherid' }], truncated: false },
    reload: vi.fn(),
  });
  render(<BuildRecipeReadiness projectId="prj_12345678" repo={repo()} />);
  expect(screen.getByText('NO RESULT YET')).toBeTruthy();
  expect(screen.getByText(/Nothing has been recorded for this repository yet/)).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Refresh' })).toBeTruthy();
});

it('explains owner-only audit access and does not fetch without an App installation', () => {
  const forbidden = new ApiError(403, { code: 'FORBIDDEN', message: 'Forbidden', details: {}, request_id: null });
  mocks.useResource.mockReturnValue({ status: 'error', error: forbidden, reload: vi.fn() });
  const { rerender } = render(<BuildRecipeReadiness projectId="prj_12345678" repo={repo()} />);
  expect(screen.getByText('Only project owners can read the build-recipe result.')).toBeTruthy();

  mocks.useResource.mockClear();
  rerender(<BuildRecipeReadiness projectId="prj_12345678" repo={repo(null)} />);
  expect(screen.getByText('No build recipe is proposed for repositories not connected through the GitHub App.')).toBeTruthy();
  expect(mocks.useResource.mock.calls.at(-1)?.[0]).toBeNull();
});

it('finds a matching recipe event on page two', async () => {
  const found = event('recipe.skipped', { reason: 'No supported build command' });
  mocks.auditEvents
    .mockResolvedValueOnce({ items: [{ ...found, subject_id: 'rep_otherid' }], next_cursor: '500' })
    .mockResolvedValueOnce({ items: [found], next_cursor: '1000' });
  const signal = new AbortController().signal;
  const data = await loadRecipeAudit('prj_12345678', repo().id, signal);

  expect(mocks.auditEvents).toHaveBeenNthCalledWith(1, 'prj_12345678', { signal, limit: 500 });
  expect(mocks.auditEvents).toHaveBeenNthCalledWith(2, 'prj_12345678', { signal, limit: 500, cursor: '500' });
  expect(data).toEqual({ items: [{ ...found, subject_id: 'rep_otherid' }, found], truncated: false });
  mocks.useResource.mockReturnValue({ status: 'ready', data, reload: vi.fn() });
  render(<BuildRecipeReadiness projectId="prj_12345678" repo={repo()} />);
  expect(screen.getByText('SKIPPED')).toBeTruthy();
  expect(screen.getByText('No supported build command')).toBeTruthy();
});

it('marks a no-result search as truncated after four pages and explains the limit', async () => {
  mocks.auditEvents
    .mockResolvedValueOnce({ items: [], next_cursor: '500' })
    .mockResolvedValueOnce({ items: [], next_cursor: '1000' })
    .mockResolvedValueOnce({ items: [], next_cursor: '1500' })
    .mockResolvedValueOnce({ items: [], next_cursor: '2000' });
  const data = await loadRecipeAudit('prj_12345678', repo().id, new AbortController().signal);

  expect(mocks.auditEvents).toHaveBeenCalledTimes(4);
  expect(data).toEqual({ items: [], truncated: true });
  mocks.useResource.mockReturnValue({ status: 'ready', data, reload: vi.fn() });
  render(<BuildRecipeReadiness projectId="prj_12345678" repo={repo()} />);
  expect(screen.getByText('NO RESULT YET')).toBeTruthy();
  expect(screen.getByText('No build-recipe result in the 2,000 most recent audit events for this project.')).toBeTruthy();
});

it('lets the owner retry a failed or invalid recipe, but not an unsupported one', async () => {
  const reload = vi.fn();
  mocks.retryBuildRecipe.mockResolvedValue({ job_id: 'job_1', queued: true });
  mocks.useResource.mockReturnValue({ status: 'ready', data: { items: [event('recipe.failed', { reason: 'Repository not found' })] }, reload });
  render(<BuildRecipeReadiness projectId="prj_12345678" repo={repo()} />);
  fireEvent.click(screen.getByRole('button', { name: 'Retry build recipe' }));
  expect(await screen.findByText(/Retry queued/)).toBeTruthy();
  expect(mocks.retryBuildRecipe).toHaveBeenCalledWith('rep_12345678');
  expect(reload).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole('button', { name: 'Refresh' }));
  expect(reload).toHaveBeenCalledTimes(2);
  cleanup();
  mocks.useResource.mockReturnValue({ status: 'ready', data: { items: [event('recipe.unsupported', { reason: 'Go' })] }, reload });
  render(<BuildRecipeReadiness projectId="prj_12345678" repo={repo()} />);
  expect(screen.queryByRole('button', { name: 'Retry build recipe' })).toBeNull();
});
