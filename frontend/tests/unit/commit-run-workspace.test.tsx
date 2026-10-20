import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import type { AssessmentDetail } from '@hackatl/frontend-transport';
const state = vi.hoisted(() => ({ detail: null as AssessmentDetail | null, cancel: vi.fn() }));
vi.mock('@/lib/api', () => ({ api: () => ({ cancelAssessment: state.cancel }) }));
vi.mock('@/lib/use-resource', () => ({ useResource: () => state.detail ? { status: 'ready', data: state.detail, reload: vi.fn() } : { status: 'loading', reload: vi.fn() } }));
import { belongsToCommit, CommitRunWorkspace } from '@/components/commit-run-workspace';
const detail = (repo = 'repo_one', sha = 'abc'): AssessmentDetail => ({ assessment: { id: 'asm_one', repo_id: repo, commit_sha: sha, state: 'COMPLETED' }, agent_runs: [], findings: [] } as unknown as AssessmentDetail);
beforeEach(() => { state.detail = null; vi.stubGlobal('matchMedia', () => ({ matches: false })); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it('rejects both sibling repositories and other commits', () => {
  expect(belongsToCommit(detail(), 'repo_one', 'abc')).toBe(true);
  expect(belongsToCommit(detail('repo_two'), 'repo_one', 'abc')).toBe(false);
  expect(belongsToCommit(detail('repo_one', 'def'), 'repo_one', 'abc')).toBe(false);
  state.detail = detail('repo_two');
  render(<CommitRunWorkspace assessmentId="asm_one" repoId="repo_one" sha="abc" fullName="acme/one" />);
  expect(screen.getByRole('alert').textContent).toContain('another repository or commit');
  expect(screen.queryByTestId('commit-reviewer')).toBeNull();
});
it('shows seven unrun agents without inventing work or replay steps', () => {
  render(<CommitRunWorkspace assessmentId={null} repoId="repo_one" sha="abc" fullName="acme/one" />);
  fireEvent.click(screen.getByRole('tab', { name: '7 agents' }));
  expect(screen.getByRole('navigation', { name: 'Security agents' }).querySelectorAll('button')).toHaveLength(7);
  expect(screen.getByRole('button', { name: 'Play replay' }).hasAttribute('disabled')).toBe(true);
  expect(screen.getByTestId('commit-agent-map').textContent).toContain('No recorded run for this commit');
});

it('can cancel the selected active run without leaving the commit', async () => {
  state.detail = detail();
  state.detail.assessment.state = 'FUNCTIONAL_REVIEW';
  state.cancel.mockResolvedValue({ cancelled: false });
  render(<CommitRunWorkspace assessmentId="asm_one" repoId="repo_one" sha="abc" fullName="acme/one" />);
  fireEvent.click(screen.getByRole('button', { name: 'Cancel assessment' }));
  expect((await screen.findByTestId('cancel-assessment-result')).textContent).toContain('Stop requested');
  expect(state.cancel).toHaveBeenCalledWith('asm_one');
});

it('maps replay position zero to no call and positions one and two to each saved call', () => {
  state.detail = detail();
  state.detail.agent_runs = [{ assessment_id: 'asm_one', agent: 'scout', status: 'succeeded', started_at: '2026-01-01', provider: 'fake', tool_calls: [{ tool_name: 'first_saved_call' }, { tool_name: 'second_saved_call' }] }] as unknown as AssessmentDetail['agent_runs'];
  render(<CommitRunWorkspace assessmentId="asm_one" repoId="repo_one" sha="abc" fullName="acme/one" />);
  fireEvent.click(screen.getByRole('tab', { name: '7 agents' }));
  const map = screen.getByTestId('commit-agent-map');
  const worker = map.querySelector('.commit-recording-worker')!;
  expect(worker.textContent).not.toContain('first_saved_call');
  fireEvent.change(screen.getByRole('slider', { name: 'Replay position' }), { target: { value: '1' } });
  expect(worker.textContent).toContain('first_saved_call');
  fireEvent.change(screen.getByRole('slider', { name: 'Replay position' }), { target: { value: '2' } });
  expect(worker.textContent).toContain('second_saved_call');
});
