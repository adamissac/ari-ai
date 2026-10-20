import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import ProjectOverview from '@/app/(console)/projects/[projectId]/page';

const mocks = vi.hoisted(() => ({ assessments: vi.fn(), reload: vi.fn(), nextCursor: 'asm_003' as string | null }));
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock('@/components/project', () => ({ useProject: () => ({
  project: { id: 'prj_one', name: 'owned', settings: { monitoring_policy: { enabled: true } } },
  repos: [], reloadRepos: mocks.reload,
}) }));
vi.mock('@/lib/api', async importOriginal => ({
  ...await importOriginal<typeof import('@/lib/api')>(),
  api: () => ({ assessments: mocks.assessments }),
}));
const asm = (id: string) => ({
  id, state: 'CREATED', commit_sha: 'a'.repeat(40), trigger: 'manual', created_at: '2026-10-17T03:00:00Z',
  usage: { llm_calls: 1, usd: 0 },
});
// Stable references per key, like the real hook, so the page's change-detection does not loop.
const EMPTY = { items: [], next_cursor: null };
const FIRST_PAGE = [asm('asm_005'), asm('asm_004'), asm('asm_003')];
const pages = new Map<string | null, unknown>();
vi.mock('@/lib/use-resource', () => ({ useResource: (key: string | null) => {
  const wanted = key?.startsWith('asm:') ? { items: FIRST_PAGE, next_cursor: mocks.nextCursor } : EMPTY;
  const prev = pages.get(key) as typeof wanted | undefined;
  const data = prev && prev.items === wanted.items && prev.next_cursor === wanted.next_cursor ? prev : wanted;
  pages.set(key, data);
  return { status: 'ready', reload: mocks.reload, data };
} }));

beforeEach(() => { mocks.assessments.mockReset(); mocks.nextCursor = 'asm_003'; });
afterEach(cleanup);

it('says the list is truncated and appends older checks, deduped by id', async () => {
  mocks.assessments.mockResolvedValue({ items: [asm('asm_003'), asm('asm_002'), asm('asm_001')], next_cursor: null });
  render(<ProjectOverview />);
  expect(screen.getByTestId('assessments-truncated').textContent).toContain('Showing the newest 3 checks');
  fireEvent.click(screen.getByTestId('load-older-assessments'));
  await waitFor(() => expect(screen.queryByTestId('assessments-truncated')).toBeNull());
  expect(mocks.assessments).toHaveBeenCalledWith('prj_one', { cursor: 'asm_003' });
  expect(screen.getAllByRole('link', { name: /^Open run & replay asm_/  }).map(a => a.getAttribute('href')?.split('/').at(-1))).toEqual(['asm_005', 'asm_004', 'asm_003', 'asm_002', 'asm_001']);
});

it('shows no truncation note when there is no next cursor', () => {
  mocks.nextCursor = null;
  render(<ProjectOverview />);
  expect(screen.queryByTestId('assessments-truncated')).toBeNull();
});

it('surfaces a failed older-page load with a retry', async () => {
  mocks.assessments.mockRejectedValueOnce(new TypeError('Failed to fetch')).mockResolvedValue({ items: [asm('asm_002')], next_cursor: null });
  render(<ProjectOverview />);
  fireEvent.click(screen.getByTestId('load-older-assessments'));
  await waitFor(() => expect(screen.getByTestId('error-state')).toBeTruthy());
  expect(screen.getByTestId('assessments-truncated')).toBeTruthy();
});
