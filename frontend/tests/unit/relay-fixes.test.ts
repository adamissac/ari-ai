import { describe, expect, it } from 'vitest';
import { agentRelay, type RelayTile } from '@/lib/relay';

const run = (agent: string, status = 'succeeded') => ({ agent: agent as RelayTile['agent'], status, tool_calls: [] });
const probeText = (findings: { kind: string; status: string }[]) => {
  const t = agentRelay({ runs: [run('probe')], findings, state: 'COMPLETED' }).find(i => i.kind === 'agent' && i.agent === 'probe');
  return t?.kind === 'agent' ? t.handoff : '';
};

describe('relay probe handoff', () => {
  it('counts confirmed explicitly; inconclusive, closed, accepted_risk and stale are not confirmed', () => {
    const findings = ['inconclusive', 'closed', 'accepted_risk', 'needs_recheck'].map(status => ({ kind: 'security', status }));
    const text = probeText(findings);
    expect(text).not.toMatch(/confirmed/);
    expect(text).toBe('Test results: 1 inconclusive. Each finding shows its recorded test.');
  });
  it('reports confirmed, ruled out, inconclusive and unconfirmed separately', () => {
    const statuses = ['validated', 'diagnosed', 'patch_proposed', 'verified', 'patch_rejected', 'unresolved', 'hardened', 'refuted', 'inconclusive', 'hypothesis'];
    expect(probeText(statuses.map(status => ({ kind: 'security', status }))))
      .toBe('Test results: 7 confirmed, 1 ruled out, 1 inconclusive, 1 still marked unconfirmed. Each finding shows its recorded test.');
  });
});
