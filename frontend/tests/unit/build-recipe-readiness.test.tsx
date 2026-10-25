import { cleanup, render, screen } from '@testing-library/react';
import type { Repository } from '@hackatl/frontend-transport';
import { ApiError } from '@hackatl/frontend-transport';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { BuildRecipeReadiness } from '@/components/onboarding/build-recipe-readiness';

const mocks = vi.hoisted(() => ({ useResource: vi.fn() }));
vi.mock('@/lib/use-resource', () => ({ useResource: mocks.useResource }));

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
  mocks.useResource.mockReturnValue({ status: 'ready', data: { items: [] }, reload: vi.fn() });
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
    data: { items: [{ ...event('recipe.failed', { reason: 'other repo' }), subject_id: 'rep_otherid' }, { ...event('recipe.skipped'), subject_id: 'rep_otherid' }] },
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
