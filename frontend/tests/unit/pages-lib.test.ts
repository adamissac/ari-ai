import type { Incident, Project } from '@hackatl/frontend-transport';
import { describe, expect, it } from 'vitest';
import { action, approvalFor, GATE_FOR, NEXT_STATES } from '@/lib/incidents';
import { draftOf, parseSettings } from '@/lib/settings';

const project = {
  id: 'prj_12345678', org_id: 'org_12345678', name: 'Payments', created_at: '2026-10-17T03:00:00Z',
  settings: {
    default_budget: { max_tokens: 400000, max_usd: 10, max_wall_clock_s: 1800 },
    monitoring_policy: { enabled: true, min_interval_s: 600, ignore_paths_only: ['tests/**', 'docs/**'], monitoring_budget: { max_tokens: 150000, max_usd: 3, max_wall_clock_s: 900 } },
    languages: ['python'],
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
