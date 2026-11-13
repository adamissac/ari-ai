import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';

const state = vi.hoisted(() => ({ items: [] as unknown[], approvals: [] as unknown[] }));

vi.mock('@/components/project', () => ({ useProject: () => ({
  project: { id: 'project-1' },
  selectedRepo: { id: 'repo-1', full_name: 'acme/payments', default_branch: 'main' },
}) }));
vi.mock('@/lib/use-resource', () => ({
  useResource: (key: string) => ({
    status: 'ready',
    data: { items: key?.includes('snapshots') ? [{ id: 'snap-1' }] : key?.includes('assessments') ? [{ id: 'asm-1', repo_id: 'repo-1' }] : key?.includes('approvals') ? state.approvals : state.items },
    error: undefined,
    reload: vi.fn(),
  }),
}));
vi.mock('@/lib/api', () => ({ api: () => ({ findings: vi.fn() }) }));

import FindingsPage from '@/app/(console)/projects/[projectId]/findings/page';

afterEach(() => {
  cleanup();
  state.items = [];
  state.approvals = [];
});

it('shows other finding counts and opens the fixed tab when nothing confirmed is open', () => {
  state.items = [{
    id: 'finding-fixed',
    assessment_id: 'asm-1',
    snapshot_id: null,
    title: 'Verified fix',
    status: 'verified',
    kind: 'security',
    severity: null,
    commit_sha: 'abcdef123456',
    updated_at: '2026-10-25T00:00:00Z',
  }];

  render(<FindingsPage />);

  expect(screen.getByText('Nothing needs a fix. 1 fixed.')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'View fixed findings' }));
  expect(screen.getByRole('tab', { name: /^Fixed/ }).getAttribute('aria-selected')).toBe('true');
  expect(within(screen.getByTestId('findings-mobile-list')).getByRole('link', { name: 'Verified fix' })).toBeTruthy();
});

it('says plainly when fixes wait for approval', () => {
  state.items = [
    { id: 'f1', assessment_id: 'asm-1', kind: 'security', status: 'diagnosed', title: 'Refund cap', commit_sha: 'a'.repeat(40), updated_at: '2026-11-01T00:00:00Z', severity: null },
  ];
  state.approvals = [{ id: 'apv-1', subject_type: 'remediation', status: 'pending' }];
  render(<FindingsPage />);
  const banner = screen.getByTestId('findings-approval-banner');
  expect(banner.textContent).toContain('1 fix is waiting for your approval');
  expect(banner.querySelector('a')?.getAttribute('href')).toContain('/approvals');
});

it('lists a finding repeated across commits once and marks the one waiting for approval', () => {
  const f = (id: string, status: string) => ({ id, assessment_id: 'asm-1', kind: 'functional', status, title: 'Refund cap', commit_sha: 'a'.repeat(40), updated_at: '2026-11-01T00:00:00Z', severity: null });
  state.items = [f('fnd-new', 'validated'), f('fnd-old', 'validated'), f('fnd-older', 'validated')];
  state.approvals = [{ id: 'apv-1', subject_type: 'remediation', subject_id: 'fnd-new', status: 'pending' }];
  render(<FindingsPage />);
  expect(screen.getByRole('tab', { name: /Needs a fix/ }).textContent).toBe('Needs a fix1');
  expect(screen.getByTestId('finding-repeats').textContent).toBe('also on 2 earlier reviews');
  expect(screen.getByTestId('finding-group-breakdown').textContent).toContain('1 waiting for your approval before Ari writes the fix');
  expect(screen.getAllByText('Waiting for your approval').length).toBeGreaterThan(0);
});
