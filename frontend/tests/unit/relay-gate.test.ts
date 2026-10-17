import { describe, expect, it } from 'vitest';
import { agentRelay, type RelayTile } from '@/lib/relay';

const run = (agent: string, status = 'succeeded') => ({ agent: agent as RelayTile['agent'], status, tool_calls: [] });

describe('relay approval gate', () => {
  const runs = ['reviewer', 'scout', 'probe', 'trace', 'diagnose', 'patch'].map(a => run(a));
  const gate = (approvals: { subject_type: string; status: string }[] | null | undefined, state: Parameters<typeof agentRelay>[0]['state'] = 'COMPLETED') => {
    const g = agentRelay({ runs, findings: [], state, approvals }).find(i => i.kind === 'gate');
    return g?.kind === 'gate' ? g : null;
  };
  it('a patch run alone does not prove a person approved', () => {
    expect(gate([])?.status).toBe('not_used');
    expect(gate([])?.text).toMatch(/No approval record/);
  });
  it('unknown approvals are not presented as approved', () => {
    expect(gate(undefined)?.status).toBe('not_reached');
    expect(gate(null)?.text).toMatch(/unknown/);
  });
  it('passes only on an approved remediation approval', () => {
    expect(gate([{ subject_type: 'remediation', status: 'approved' }])?.status).toBe('passed');
    expect(gate([{ subject_type: 'scope', status: 'approved' }])?.status).toBe('not_used');
  });
  it('declined and pending are shown as such', () => {
    expect(gate([{ subject_type: 'remediation', status: 'declined' }])?.status).toBe('declined');
    expect(gate([{ subject_type: 'remediation', status: 'pending' }], 'REMEDIATION')?.status).toBe('waiting');
    expect(gate([], 'AWAITING_APPROVAL')?.status).toBe('waiting');
  });
});
