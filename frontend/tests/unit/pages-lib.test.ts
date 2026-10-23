import type { Incident, PatchView, Project } from '@hackatl/frontend-transport';
import { describe, expect, it } from 'vitest';
import { acceptedVerifications, action, approvalFor, closureBlockers, GATE_FOR, NEXT_STATES, patchEvidence, regressionEvidence } from '@/lib/incidents';
import { draftOf, parseSettings } from '@/lib/settings';

const project = {
  id: 'prj_12345678', org_id: 'org_12345678', name: 'Payments', created_at: '2026-10-17T03:00:00Z',
  settings: {
    default_budget: { max_tokens: 400000, max_usd: 10, max_wall_clock_s: 1800 },
    monitoring_policy: { enabled: true, min_interval_s: 600, ignore_paths_only: ['tests/**', 'docs/**'], monitoring_budget: { max_tokens: 150000, max_usd: 3, max_wall_clock_s: 900 } },
    languages: ['python'],
    delivery_mode: 'pull_request',
    delivery_authorized_by: null, // server-owned; the form always sends null
  },
} as unknown as Project;

describe('project settings form', () => {
  it('round-trips the saved settings without loss', () => {
    const parsed = parseSettings(draftOf(project));
    expect(parsed).toEqual({ settings: project.settings });
  });

  it('rejects invalid numbers instead of coercing them', () => {
    const d = draftOf(project);
    expect(parseSettings({ ...d, maxTokens: '-1' })).toEqual({ error: expect.stringContaining('Default budget') });
    expect(parseSettings({ ...d, monUsd: 'abc' })).toEqual({ error: expect.stringContaining('Monitoring budget') });
    expect(parseSettings({ ...d, maxWall: '0' })).toHaveProperty('error');
    expect(parseSettings({ ...d, interval: '1.5' })).toHaveProperty('error');
    expect(parseSettings({ ...d, name: '  ' })).toHaveProperty('error');
    expect(parseSettings({ ...d, languages: ' , ' })).toHaveProperty('error');
  });

  it('splits globs per line and drops blanks', () => {
    const parsed = parseSettings({ ...draftOf(project), ignore: 'a/**\n\n  b/*.md  \n' });
    expect('settings' in parsed && parsed.settings.monitoring_policy.ignore_paths_only).toEqual(['a/**', 'b/*.md']);
  });
});

describe('incident helpers', () => {
  it('builds a complete IncidentAction with explicit nulls', () => {
    const a = action('transition', { target_state: 'analysis', note: 'go' });
    expect(a.kind).toBe('transition');
    expect(a.target_state).toBe('analysis');
    expect(a.gate).toBeNull();
    expect(a.evidence).toEqual([]);
    expect(Object.keys(a)).toHaveLength(19);
  });

  it('never offers triaged as a transition (triage is its own action) and gates the NIST steps', () => {
    expect(NEXT_STATES.reported).not.toContain('triaged');
    expect(NEXT_STATES.closed).toEqual([]);
    expect(GATE_FOR.containment).toBe('containment');
    expect(GATE_FOR.closed).toBe('closure');
    expect(GATE_FOR.analysis).toBeUndefined();
  });

  it('uses the latest approval for a gate', () => {
    const inc = { approvals: [
      { gate: 'containment', status: 'declined' },
      { gate: 'containment', status: 'approved' },
    ] } as unknown as Incident;
    expect(approvalFor(inc, 'containment')?.status).toBe('approved');
    expect(approvalFor(inc, 'closure')).toBeUndefined();
  });
});

describe('incident closure helpers', () => {
  const view = (verdict: 'accepted' | 'rejected' | null) => ({
    patch: { id: 'pat_1', finding_id: 'fnd_1', attempt: 2, diff_artifact_id: 'art_diff', diff_sha256: 'a'.repeat(64) },
    verification: verdict ? { id: `ver_${verdict}`, verdict } : null,
  }) as unknown as PatchView;

  it('pins patch diffs and Fortify tests as hash-carrying artifact evidence', () => {
    expect(patchEvidence('fnd_1', [view('accepted')], {})).toEqual([]);
    const [opt] = patchEvidence('fnd_1', [view('accepted')], { art_diff: 'c'.repeat(64) });
    if (!opt) throw new Error('expected one evidence option');
    expect(opt.ref).toMatchObject({ kind: 'artifact', artifact_id: 'art_diff', sha256: 'c'.repeat(64), provenance: 'agent:patch' });
    expect(opt.label).toContain('stored copy redacted');
    expect(opt.regression).toBe(false);
    expect(opt.label).toContain('Verify accepted');
    const reg = regressionEvidence('fnd_1', 'art_test', 'b'.repeat(64));
    expect(reg.regression).toBe(true);
    expect(reg.ref).toMatchObject({ artifact_id: 'art_test', sha256: 'b'.repeat(64), provenance: 'agent:fortify', path: null, span: null });
  });

  it('offers only accepted verifications for linking', () => {
    expect(acceptedVerifications([view('accepted'), view('rejected'), view(null)])).toEqual(['ver_accepted']);
  });

  it('lists every outstanding closure requirement and none once closed', () => {
    const base = { state: 'recovery', closure_criteria: [], lessons_learned: null, lessons_learned_evidence: [], approvals: [] } as unknown as Incident;
    expect(closureBlockers(base)).toHaveLength(3);
    const ready = {
      ...base,
      closure_criteria: [{ key: 'tests', description: 'd', satisfied: true, evidence: [{}], satisfied_by: 'usr_1' }, { key: 'comms', description: 'd', satisfied: false, evidence: [], satisfied_by: null }],
      lessons_learned: 'keep the tenant test', lessons_learned_evidence: [{}],
      approvals: [{ gate: 'closure', status: 'approved' }],
    } as unknown as Incident;
    expect(closureBlockers(ready)).toEqual(['Satisfy with evidence: comms.']);
    expect(closureBlockers({ ...base, state: 'closed' } as Incident)).toEqual([]);
  });
});
