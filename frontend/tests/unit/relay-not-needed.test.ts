import { describe, expect, it } from 'vitest';
import { agentRelay, earlyEndNote, type RelayTile } from '@/lib/relay';

const run = (agent: string, status = 'succeeded') => ({ agent: agent as RelayTile['agent'], status, tool_calls: [] });
const tile = (items: ReturnType<typeof agentRelay>, agent: string) => {
  const t = items.find(i => i.kind === 'agent' && i.agent === agent);
  return t?.kind === 'agent' ? t : undefined;
};

describe('relay not-needed / not-reached states', () => {
  const runs = [run('reviewer'), run('scout')];
  it('agents that never ran show not needed once the assessment completed', () => {
    const items = agentRelay({ runs, findings: [], state: 'COMPLETED', skipNote: 'no confirmed findings' });
    for (const agent of ['probe', 'trace', 'diagnose', 'patch', 'verify', 'fortify']) {
      expect(tile(items, agent)?.status).toBe('not_needed');
      expect(tile(items, agent)?.statusText).toBe('Not needed');
      expect(tile(items, agent)?.handoff).toContain('no confirmed findings');
    }
    expect(tile(items, 'scout')?.status).toBe('done');
  });
  it('falls back to a generic line when no skip note is recorded', () => {
    const t = tile(agentRelay({ runs, findings: [], state: 'COMPLETED' }), 'probe');
    expect(t?.handoff).toBe('Not needed — the run ended before this step had work.');
  });
  it('an unfinished agent is not reached, never not needed, when the run failed or was cancelled', () => {
    for (const state of ['FAILED', 'CANCELLED', 'BUDGET_EXHAUSTED'] as const) {
      const t = tile(agentRelay({ runs, findings: [], state }), 'verify');
      expect(t?.status).toBe('not_reached');
      expect(t?.statusText).toBe('Not reached');
      expect(t?.handoff).toBe('The run ended before this step was reached.');
    }
  });
  it('agents with no run stay not run while the assessment is still going', () => {
    const t = tile(agentRelay({ runs, findings: [], state: 'VALIDATION' }), 'probe');
    expect(t?.status).toBe('not_run');
  });
});

describe('earlyEndNote', () => {
  const ev = (state: string | null, message: string) => ({ type: 'assessment.state_changed', state, message });
  it('reads the recorded early-end reason from the reporting transition', () => {
    expect(earlyEndNote([ev('RECON', ''), ev('REPORTING', 'no hypotheses')])).toBe('no hypotheses');
  });
  it('prefers an explicit skipped-phase note and ignores later empty transitions', () => {
    const events = [ev('RECON', ''), ev('VALIDATION', 'skipped (no hypotheses); awaiting functional remediation approval'), ev('COMPLETED', 'assessment completed')];
    expect(earlyEndNote(events)).toBe('no hypotheses');
  });
  it('is null for a full-chain run and for non-transition events', () => {
    expect(earlyEndNote([ev('REPORTING', '')])).toBeNull();
    expect(earlyEndNote([{ type: 'agent_run.finished', message: 'done' }])).toBeNull();
  });
});
