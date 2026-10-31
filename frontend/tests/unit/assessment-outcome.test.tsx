import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import type { AgentRun, Assessment, Finding } from '@hackatl/frontend-transport';
import { AssessmentOutcome } from '@/components/assessment-outcome';
import { coverage, outcomeCounts, stoppedExplanation } from '@/lib/assessment-outcome';
import { agentRelay } from '@/lib/relay';

vi.mock('next/link', () => ({ default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => <a href={href} {...rest}>{children}</a> }));
afterEach(cleanup);

const SHA = 'a'.repeat(40);
const run = (agent: string, status = 'succeeded', step_key = agent, provider_mode = 'live') => ({ agent, status, step_key, provider_mode, tool_calls: [] });
const assessment = (state: Assessment['state'], error: Assessment['error'] = null) => ({
  id: 'asm_1', project_id: 'prj_1', snapshot_id: null, commit_sha: SHA, repo_id: 'rep_1', scope_id: 'scp_1', trigger: 'manual',
  reassessment_request_id: null, state, budget: {}, usage: {}, error, created_by: null, created_at: '', updated_at: '', completed_at: null,
}) as unknown as Assessment;
const ALL = ['reviewer', 'scout', 'probe', 'trace', 'diagnose', 'patch', 'verify', 'fortify'];

function view(state: Assessment['state'], findings: Finding[], runs: ReturnType<typeof run>[], skipNote: string | null = null, error: Assessment['error'] = null) {
  const relay = agentRelay({ runs: runs as never, findings, state, approvals: [], skipNote });
  return render(<AssessmentOutcome assessment={assessment(state, error)} findings={findings} runs={runs as unknown as AgentRun[]} approvals={[]} relay={relay} skipNote={skipNote} projectId="prj_1" />);
}

it('counts findings, proposals, approvals and verified fixes only from records', () => {
  const findings = [
    { id: 'f1', kind: 'security', status: 'hardened' },
    { id: 'f2', kind: 'functional', status: 'patch_rejected' },
    { id: 'f3', kind: 'security', status: 'hypothesis' },
    { id: 'f4', kind: 'security', status: 'refuted' },
  ];
  const runs = [run('patch', 'succeeded', 'patch:f1'), run('patch', 'succeeded', 'patch:f2'), run('patch', 'failed', 'patch:f3')];
  const approvals = [{ subject_type: 'remediation', status: 'approved' }, { subject_type: 'remediation', status: 'declined' }, { subject_type: 'scope', status: 'approved' }];
  expect(outcomeCounts(findings, runs, approvals)).toEqual({
    findings: 4, confirmed: 2, ruledOut: 1, unconfirmed: 1, fixesProposed: 2, fixesVerified: 1, approved: 1, declined: 1, pending: 0,
  });
});

it('calls a no-findings run limited when the security agents never tested anything', () => {
  const relay = agentRelay({ runs: [run('reviewer')] as never, findings: [], state: 'COMPLETED', approvals: [], skipNote: 'no entry points' });
  const c = coverage(relay, [run('reviewer')], 'no entry points');
  expect(c.kind).toBe('limited');
  expect(c.kind === 'limited' && c.gaps.join(' ')).toContain('security agents did not test anything: the run ended early (no entry points)');
});

it('flags non-live model turns as limited coverage', () => {
  const runs = ALL.map(a => run(a, 'succeeded', a, 'fake'));
  const relay = agentRelay({ runs: runs as never, findings: [], state: 'COMPLETED', approvals: [], skipNote: null });
  expect(coverage(relay, runs, null).kind).toBe('limited');
});

it('a fully covered clean run still says it is not proof of security', () => {
  view('COMPLETED', [], ALL.map(a => run(a)));
  const panel = screen.getByTestId('assessment-outcome');
  expect(panel.dataset.outcome).toBe('clean');
  expect(panel.textContent).toContain('It is not proof that the application is secure.');
});

it('a limited clean run says not to read it as a clean security result', () => {
  view('COMPLETED', [], [run('reviewer')], 'no confirmed findings');
  expect(screen.getByTestId('assessment-outcome').dataset.outcome).toBe('clean-limited');
  expect(screen.getByText(/do not read this as a clean security result/)).toBeTruthy();
});

it('a failed run explains the cause and links to restart the same commit', () => {
  view('FAILED', [], [run('reviewer'), run('scout', 'failed')], null, { code: 'SANDBOX_START_FAILED', message: 'boom', details: {}, request_id: null });
  const panel = screen.getByTestId('assessment-outcome');
  expect(panel.dataset.outcome).toBe('stopped');
  expect(panel.textContent).toContain('isolated test copy');
  expect(panel.textContent).toContain('This is not a clean result.');
  const retry = screen.getByTestId('outcome-retry');
  expect(retry.getAttribute('href')).toBe(`/projects/prj_1/commits?repo=rep_1&commit=${SHA}#start-assessment`);
});

it('budget exhaustion points at the budget setting', () => {
  expect(stoppedExplanation('BUDGET_EXHAUSTED', null).next).toContain('Settings');
  view('BUDGET_EXHAUSTED', [], []);
  expect(screen.getByText('Assessment budget in Settings →')).toBeTruthy();
});

it('renders nothing while the check is still running', () => {
  const { container } = view('RECON', [], [run('reviewer')]);
  expect(container.textContent).toBe('');
});
