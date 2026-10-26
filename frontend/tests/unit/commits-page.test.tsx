import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';

const state = vi.hoisted(() => ({ sha: 'b'.repeat(40) }));
vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn() }),
  useSearchParams: () => ({ get: (key: string) => key === 'commit' ? state.sha : null, toString: () => `repo=repo-1&commit=${state.sha}` }),
}));
vi.mock('@/components/project', () => ({ useProject: () => ({
  project: { id: 'project-1', settings: { monitoring_policy: { enabled: false } } },
  selectedRepo: { id: 'repo-1', full_name: 'acme/payments-lite', default_branch: 'main' },
}) }));
vi.mock('@/components/commit-assessment-chips', () => ({
  CommitAssessmentProvider: ({ children }: { children: React.ReactNode }) => children,
  CommitAssessmentChip: () => null,
}));
vi.mock('@/components/assessment-history', () => ({ AssessmentList: () => null }));
vi.mock('@/components/start-assessment', () => ({ StartAssessment: () => null }));
vi.mock('@/lib/use-resource', () => ({
  useResource: (key: string | null) => {
    const run = { id: 'asm-1', repo_id: 'repo-1', commit_sha: state.sha, state: 'COMPLETED', created_at: '2026-10-25T00:00:00Z', trigger: 'manual', usage: { llm_calls: 1, usd: 0 } };
    const agentRun = (id: string, agent: 'scout' | 'trace') => ({
      id, assessment_id: 'asm-1', agent, step_key: 'recon', attempt: 1, status: 'succeeded',
      provider_mode: 'fake', model_id: 'scripted-model', started_at: '2026-10-25T00:00:00Z', ended_at: '2026-10-25T00:00:10Z',
      usage: { input_tokens: 10, output_tokens: 20, cache_read_input_tokens: 0, usd: 0, sandbox_seconds: 1, llm_calls: 1, tool_calls: 1 },
      tool_calls: [{ turn: 0, tool_name: `read_${agent}`, outcome: 'ok', error_code: null, duration_ms: 10, input_sha256: 'sha256', output_artifact_id: null }],
      error: null, prompt_version: null, input_artifact_id: null, output_artifact_id: null, transcript_artifact_id: null,
    });
    const detail = {
      assessment: { id: 'asm-1', repo_id: 'repo-1', commit_sha: state.sha, state: 'COMPLETED', project_id: 'project-1' },
      agent_runs: [agentRun('scout-run', 'scout'), agentRun('trace-run', 'trace')],
      findings: [],
    };
    const data = key?.startsWith('commits:') ? { items: [{ sha: 'a'.repeat(40), message: 'GitHub commit', committed_at: '2026-10-24T00:00:00Z' }], available: true, reason: null }
      : key?.startsWith('commits-asm:') ? { items: [run], next_cursor: null }
      : key?.startsWith('commits-findings:') ? { items: [], next_cursor: null }
      : key?.startsWith('commit-agent-detail:') ? detail
      : { items: [], next_cursor: null };
    return { status: 'ready', data, error: undefined, refreshError: undefined, reload: vi.fn() };
  },
}));

import CommitsPage from '@/app/(console)/projects/[projectId]/commits/page';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
beforeEach(() => { vi.stubGlobal('matchMedia', () => ({ matches: false })); });

it('merges GitHub and assessment-only commits and switches to the recorded agents tab', () => {
  render(<CommitsPage />);
  expect(screen.getByTestId(`commit-row-${'a'.repeat(40)}`)).toBeTruthy();
  expect(screen.getByTestId(`commit-row-${state.sha}`)).toBeTruthy();
  fireEvent.click(screen.getByRole('tab', { name: '7 agents' }));
  const recordedMap = screen.getByTestId('commit-agent-map');
  expect(recordedMap.querySelector('.amap-grid-compact')).toBeTruthy();
  expect(recordedMap.querySelector('.amap-rail-compact')).toBeTruthy();
  expect(recordedMap.nextElementSibling?.getAttribute('data-testid')).toBe('agent-team');
  expect(screen.getByTestId('agent-team').querySelectorAll('button[data-testid^="agent-"]')).toHaveLength(8);
  expect(screen.getByTestId('agent-run-scout-run').textContent).toContain('Test provider (scripted)');

  const phase = [...screen.getByTestId('commit-agent-map').querySelectorAll('.amap-phase')]
    .find(button => button.textContent === 'Trace')!;
  fireEvent.click(phase);
  expect(phase.getAttribute('aria-pressed')).toBe('true');
  expect(screen.getByTestId('demo-agent-trace').getAttribute('aria-pressed')).toBe('true');
  expect(screen.getByRole('slider', { name: 'Replay position' }).getAttribute('value')).toBe('1');
});
