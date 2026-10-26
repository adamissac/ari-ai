import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import type { AssessmentDetail } from '@hackatl/frontend-transport';
import { DEMO_REPOS } from '@/lib/demo/data';
import { analyze } from '@/lib/demo/scenarios';
const state = vi.hoisted(() => ({
  detail: null as AssessmentDetail | null,
  cancel: vi.fn(),
  patchPages: {} as Record<string, unknown>,
  resourceKeys: [] as string[],
}));
vi.mock('@/lib/api', () => ({ api: () => ({ cancelAssessment: state.cancel }) }));
vi.mock('@/lib/use-resource', () => ({
  useResource: (key: string | null) => {
    if (key?.startsWith('commit-review-patches:')) {
      state.resourceKeys.push(key);
      const findingId = key.slice('commit-review-patches:'.length);
      return state.patchPages[findingId] ?? { status: 'ready', data: { items: [] }, reload: vi.fn() };
    }
    return state.detail ? { status: 'ready', data: state.detail, reload: vi.fn() } : { status: 'loading', reload: vi.fn() };
  },
}));
import { belongsToCommit, CommitRunWorkspace, type LiveCommitView } from '@/components/commit-run-workspace';
const detail = (repo = 'repo_one', sha = 'abc'): AssessmentDetail => ({ assessment: { id: 'asm_one', repo_id: repo, commit_sha: sha, state: 'COMPLETED', project_id: 'prj_one' }, agent_runs: [], findings: [] } as unknown as AssessmentDetail);
const finding = (id: string, kind: 'functional' | 'security', title: string, path: string) => ({
  id,
  assessment_id: 'asm_one',
  snapshot_id: null,
  commit_sha: 'abc',
  kind,
  title,
  status: 'verified',
  severity: { level: 'high' },
  subject_refs: [`target/${path}`],
  expectation_ids: [],
  evidence: [{ path: `target/${path}`, span: { start_line: 4, end_line: 9 } }],
  confidence: 1,
  produced_by_run_id: 'scout-run',
  history: [],
  standards: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}) as unknown as AssessmentDetail['findings'][number];
beforeEach(() => {
  state.detail = null;
  state.patchPages = {};
  state.resourceKeys = [];
  vi.stubGlobal('matchMedia', () => ({ matches: false }));
});
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

it('shows an honest empty state instead of inventing work when nothing has run', () => {
  render(<CommitRunWorkspace assessmentId={null} repoId="repo_one" sha="abc" fullName="acme/one" />);
  expect(screen.getByText(/Nothing to review yet/)).toBeTruthy();
  fireEvent.click(screen.getByRole('tab', { name: '7 agents' }));
  expect(screen.getByTestId('commit-agent-map').textContent).toContain('No replay yet');
});

it('shows quick-read agent outcomes in a compact preview before revealing its replay', () => {
  const repo = DEMO_REPOS[0]!;
  const commit = repo.commits[0]!;
  const liveView: LiveCommitView = {
    repo,
    commit,
    analysis: analyze(repo, commit),
    live: { model: 'scripted-model', truncated: false, htmlUrl: '' },
  };
  render(<CommitRunWorkspace assessmentId={null} repoId="repo_one" sha="abc" fullName="acme/one" liveView={liveView} />);

  fireEvent.click(screen.getByRole('tab', { name: '7 agents' }));
  const summary = screen.getByTestId('commit-agent-summary');
  expect(screen.getByTestId('commit-agent-map').textContent).toContain('Preview · nothing executed');
  expect([...summary.querySelectorAll('li > span:first-child')].map(node => node.textContent)).toEqual([
    'Scout', 'Probe', 'Trace', 'Diagnose', 'Patch', 'Fortify', 'Verify',
  ]);
  expect(summary.querySelector('li')?.textContent).toContain(liveView.analysis.agents[0]!.status === 'done' ? 'Done' : 'Not run');
  expect(summary.textContent).toContain(liveView.analysis.agents[0]!.outcome);
  expect(screen.getByRole('button', { name: 'Watch the replay' }).getAttribute('aria-expanded')).toBe('false');

  fireEvent.click(screen.getByRole('button', { name: 'Watch the replay' }));
  expect(screen.getByTestId('commit-agent-map').querySelector('.amap-grid-compact')).toBeTruthy();
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

it('plays the recorded tool calls back on the sector map in saved order', () => {
  state.detail = detail();
  state.detail.agent_runs = [{
    assessment_id: 'asm_one', agent: 'scout', step_key: 'recon', status: 'succeeded',
    started_at: '2026-01-01T00:00:00Z', ended_at: '2026-01-01T00:00:10Z', provider_mode: 'fake',
    tool_calls: [
      { turn: 0, tool_name: 'first_saved_call', outcome: 'ok', error_code: null, duration_ms: 5 },
      { turn: 1, tool_name: 'second_saved_call', outcome: 'ok', error_code: null, duration_ms: 5 },
    ],
  }] as unknown as AssessmentDetail['agent_runs'];
  render(<CommitRunWorkspace assessmentId="asm_one" repoId="repo_one" sha="abc" fullName="acme/one" />);
  fireEvent.click(screen.getByRole('tab', { name: '7 agents' }));
  expect(screen.getByTestId('commit-agent-summary').querySelectorAll('li')).toHaveLength(7);
  expect(screen.queryByTestId('demo-agent-now')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Watch the replay' }));
  const map = screen.getByTestId('commit-agent-map');
  expect(map.querySelectorAll('nav[aria-label="Agents in orchestrator order"] button')).toHaveLength(7);
  const now = screen.getByTestId('demo-agent-now');
  expect(now.textContent).toContain('first_saved_call');
  fireEvent.change(screen.getByRole('slider', { name: 'Replay position' }), { target: { value: '1' } });
  expect(now.textContent).toContain('second_saved_call');
});

it('shows a flat quick glance of every finding with locations and patch verification', () => {
  const run = detail();
  run.findings = [
    finding('fnd_security', 'security', 'SQL injection', 'src/payments.py'),
    finding('fnd_functional', 'functional', 'Refund total mismatch', 'src/refunds.py'),
    finding('fnd_pending', 'security', 'Unverified patch', 'src/auth.py'),
    finding('fnd_hidden', 'functional', 'Additional finding', 'src/extra.py'),
  ];
  state.detail = run;
  state.patchPages.fnd_security = {
    status: 'ready',
    data: { items: [{ patch: { files_changed: ['src/payments.py', 'src/query.py'], diff_artifact_id: 'art-diff' }, verification: { verdict: 'accepted' } }] },
    reload: vi.fn(),
  };
  state.patchPages.fnd_functional = {
    status: 'ready',
    data: { items: [{ patch: { files_changed: ['src/refunds.py'], diff_artifact_id: 'art-rejected' }, verification: { verdict: 'rejected' } }] },
    reload: vi.fn(),
  };
  state.patchPages.fnd_pending = {
    status: 'ready',
    data: { items: [{ patch: { files_changed: ['src/auth.py'], diff_artifact_id: 'art-pending' }, verification: null }] },
    reload: vi.fn(),
  };

  render(<CommitRunWorkspace assessmentId="asm_one" repoId="repo_one" sha="abc" fullName="acme/one" />);

  const rows = screen.getAllByTestId('commit-finding');
  expect(rows).toHaveLength(3);
  const rowText = (index: number) => rows[index]?.textContent ?? '';
  expect(rowText(0)).toContain('SQL injection');
  expect(rowText(0)).toContain('src/payments.py:4–9');
  expect(rowText(0)).toContain('src/payments.py, src/query.py');
  expect(rowText(0)).toContain('Verified ✓');
  expect(rowText(1)).toContain('Refund total mismatch');
  expect(rowText(1)).toContain('Not verified');
  expect(rowText(2)).toContain('Pending');
  expect(screen.queryByText('Additional finding')).toBeNull();
  const fullRunLink = screen.getByRole('link', { name: 'Open full run' });
  expect(fullRunLink.parentElement?.textContent).toContain('+1 more ·');
  expect(fullRunLink.getAttribute('href')).toBe('/projects/prj_one/assessments/asm_one?repo=repo_one');
  expect(screen.getByRole('link', { name: 'SQL injection' }).getAttribute('href')).toBe('/projects/prj_one/findings/fnd_security');
  expect(state.resourceKeys).toContain('commit-review-patches:fnd_security');
  const fixSummary = rows[0]?.querySelector('summary');
  expect(fixSummary?.textContent).toBe('Show the fix');
  expect(fixSummary?.closest('details')?.hasAttribute('open')).toBe(false);
  if (fixSummary) fireEvent.click(fixSummary);
  expect(fixSummary?.closest('details')?.hasAttribute('open')).toBe(true);
  expect(rows[0]?.querySelector('button')?.textContent).toContain('View diff');
});

it('shows no fix when a finding has no patch record', () => {
  const run = detail();
  run.findings = [finding('fnd_unpatched', 'security', 'Unpatched finding', 'src/app.py')];
  state.detail = run;

  render(<CommitRunWorkspace assessmentId="asm_one" repoId="repo_one" sha="abc" fullName="acme/one" />);

  expect(screen.getByTestId('commit-finding').textContent).toContain('No fix yet');
});
