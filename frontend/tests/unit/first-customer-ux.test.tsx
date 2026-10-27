import { ApiError } from '@hackatl/frontend-transport';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

const state = vi.hoisted(() => ({ approvals: [] as unknown[], findings: [] as unknown[], assessments: [] as unknown[] }));

vi.mock('@/components/project', () => ({ useProject: () => ({
  project: { id: 'prj_1' },
  selectedRepo: { id: 'rep_1', full_name: 'acme/payments', default_branch: 'main' },
}) }));
vi.mock('@/components/session', () => ({ useSession: () => ({ me: { user: { id: 'usr_me' } } }) }));
vi.mock('@/lib/action-key', () => ({ useActionKeys: () => ({ keyFor: () => 'key', done: () => {} }) }));
vi.mock('@/lib/use-resource', () => ({
  useResource: (key: string | null) => ({
    status: 'ready',
    data: { items: key?.startsWith('approvals') ? state.approvals : key?.includes('assessments') ? state.assessments : state.findings, next_cursor: null },
    error: undefined,
    reload: vi.fn(),
  }),
}));

import ApprovalsPage from '@/app/(console)/projects/[projectId]/approvals/page';
import FindingsPage from '@/app/(console)/projects/[projectId]/findings/page';
import { ErrorState } from '@/components/ui';
import { describeError } from '@/lib/api';

afterEach(() => {
  cleanup();
  state.approvals = [];
  state.findings = [];
  state.assessments = [];
});

const apiError = (status: number, code: ConstructorParameters<typeof ApiError>[1]['code'], message: string) => new ApiError(status, { code, message, details: {}, request_id: 'req_1' });

describe('error states say what to do next', () => {
  it('turns a GitHub/subsystem outage into a recovery step', () => {
    const e = describeError(apiError(503, 'SUBSYSTEM_UNAVAILABLE', 'could not read the latest commit from GitHub'));
    expect(e.title).toBe('Request failed (503)');
    expect(e.recovery).toMatch(/nothing was started/);
    expect(e.recovery).toMatch(/Ari GitHub App/);
  });

  it('explains missing access and links back to projects for 403 and 404', () => {
    expect(describeError(apiError(403, 'FORBIDDEN', 'not a member')).recovery).toMatch(/Ask a project owner/);
    render(<ErrorState error={apiError(404, 'NOT_FOUND', 'project not found')} onRetry={() => {}} context="Could not load project" />);
    expect(screen.getByTestId('error-recovery').textContent).toContain('choose it again');
    expect(screen.getByRole('link', { name: 'Back to projects' }).getAttribute('href')).toBe('/connect');
    expect(screen.getByRole('button', { name: 'Retry' })).toBeTruthy();
  });

  it('keeps transient failures to retry only', () => {
    render(<ErrorState error={apiError(503, 'SUBSYSTEM_UNAVAILABLE', 'down')} onRetry={() => {}} />);
    expect(screen.queryByRole('link', { name: 'Back to projects' })).toBeNull();
    expect(describeError(new TypeError('Failed to fetch')).recovery).toBe('Check your connection, then retry.');
  });
});

describe('approval inbox explains who decides and what is allowed', () => {
  const approval = (over: Record<string, unknown>) => ({
    id: 'apv_1', project_id: 'prj_1', subject_type: 'remediation', subject_id: 'asm_1', status: 'pending',
    requested_by: 'usr_me', requested_at: '2026-10-27T00:00:00Z', decided_by: null, decided_at: null, reason: null, ...over,
  });

  it('names the subject in plain words and says why the requester cannot approve', () => {
    state.approvals = [approval({})];
    render(<ApprovalsPage />);
    expect(screen.getByText('Candidate fix')).toBeTruthy();
    expect(screen.getByText(/requested by you/)).toBeTruthy();
    expect(screen.getByTestId('approval-self-note').textContent).toContain('another project member must approve it');
    expect((screen.getByRole('button', { name: 'Approve remediation' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('lets a different member approve without the self-approval note', () => {
    state.approvals = [approval({ requested_by: 'usr_other', subject_type: 'pr' })];
    render(<ApprovalsPage />);
    expect(screen.getByText('Pull request for a verified fix')).toBeTruthy();
    expect(screen.queryByTestId('approval-self-note')).toBeNull();
    expect((screen.getByRole('button', { name: 'Approve pr' }) as HTMLButtonElement).disabled).toBe(false);
  });

  it('describes the execution boundary when nothing is pending', () => {
    render(<ApprovalsPage />);
    expect(screen.getByText(/never merges or deploys on its own/)).toBeTruthy();
  });
});

describe('findings before the first review', () => {
  it('says no review has run and links to start one', () => {
    render(<FindingsPage />);
    expect(screen.getByTestId('findings-no-review').textContent).toContain('Ari has not reviewed acme/payments yet');
    expect(screen.getByRole('link', { name: 'Run a review' }).getAttribute('href')).toBe('/projects/prj_1/commits?repo=rep_1#start-assessment');
  });

  it('keeps the normal empty state once a review has run', () => {
    state.assessments = [{ id: 'asm_1', repo_id: 'rep_1' }];
    render(<FindingsPage />);
    expect(screen.queryByTestId('findings-no-review')).toBeNull();
    expect(screen.getByText('No open findings in this list.')).toBeTruthy();
  });
});
