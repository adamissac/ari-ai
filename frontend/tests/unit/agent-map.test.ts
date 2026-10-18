import { describe, expect, it } from 'vitest';
import { affected, componentStates, coreComponent, isRedTeam, issueComponent, plainStep, redTeamEnd, stepComponent, ticks } from '@/lib/demo/agent-map';
import { DEMO_REPOS } from '@/lib/demo/data';
import { analyze } from '@/lib/demo/scenarios';

const repo = DEMO_REPOS.find(r => r.name === 'payments-api')!;
const commit = repo.commits.find(c => c.scenario === 'authz')!;
const analysis = analyze(repo, commit);

describe('agent map', () => {
  it('pins every agent step to a part of the app, in orchestrator order', () => {
    const all = ticks(analysis, repo);
    expect(all).toHaveLength(analysis.agents.reduce((n, a) => n + a.steps.length, 0));
    expect(all[0]!.agent).toBe('scout');
    expect(all.every(t => repo.components.some(c => c.id === t.component))).toBe(true);
  });

  it('routes test users to auth and blocked outbound calls to the edge', () => {
    const base = { result: '', ms: 1, outcome: 'ok' as const };
    expect(stepComponent({ ...base, tool: 'fixture.identities', input: 'cus_a, cus_b' }, repo)).toBe('auth');
    expect(stepComponent({ ...base, tool: 'http.request', input: 'GET https://api.stripe.com', outcome: 'denied' }, repo)).toBe('edge');
    expect(stepComponent({ ...base, tool: 'sandbox.start', input: 'x' }, repo)).toBe(coreComponent(repo));
  });

  it('leaves untouched parts out and ends with the changed service fixed', () => {
    const all = ticks(analysis, repo);
    const touched = affected(all, repo);
    const end = componentStates(all, all.length, repo, analysis, true);
    expect(end[coreComponent(repo)]).toBe('fixed');
    for (const c of repo.components) if (!touched.has(c.id)) expect(end[c.id]).toBe('outside');
    const start = componentStates(all, 0, repo, analysis, true);
    expect(Object.values(start).every(s => s === 'waiting' || s === 'outside')).toBe(true);
    const mid = componentStates(all, 3, repo, analysis, true, all[3]);
    expect(Object.values(mid)).toContain('checking');
  });

  it('turns the part red exactly when Probe confirms, then Trace and the blue team work only on it', () => {
    const all = ticks(analysis, repo);
    const issue = issueComponent(analysis, repo)!;
    const verdict = redTeamEnd(all);
    expect(all[verdict - 1]!.agent).toBe('probe');
    // Before Probe's last step: nothing is red, parts looked at wait for proof.
    const before = componentStates(all, verdict - 1, repo, analysis, true);
    expect(Object.values(before)).not.toContain('issue');
    expect(Object.values(before)).toContain('scanned');
    expect(Object.values(before)).not.toContain('clear');
    // Probe's verdict: the confirmed part is red, the other parts it looked at are clear.
    const after = componentStates(all, verdict, repo, analysis, true);
    expect(after[issue]).toBe('issue');
    expect(Object.values(after)).not.toContain('scanned');
    // Every step after the red team (Trace, Diagnose, Patch, Fortify, Verify) is on the red part.
    const later = all.slice(verdict);
    expect(later.map(t => t.agent)).toEqual(expect.arrayContaining(['trace', 'diagnose', 'patch', 'fortify', 'verify']));
    expect(later.every(t => t.component === issue)).toBe(true);
    // It stays red while they work, even when it is the part being worked on.
    for (let p = verdict; p < all.length; p++) expect(componentStates(all, p, repo, analysis, true, all[p])[issue]).toBe('issue');
    // A fix that Verify did not accept leaves it red.
    expect(componentStates(all, all.length, repo, analysis, false)[issue]).toBe('issue');
  });

  it('stops after the red team on a clean commit: nothing turns red and the blue team never runs', () => {
    for (const scenario of ['clean', 'dependency'] as const) {
      const clean = repo.commits.find(c => c.scenario === scenario)!;
      const a = analyze(repo, clean);
      const all = ticks(a, repo);
      expect(issueComponent(a, repo)).toBeNull();
      expect(all.every(t => isRedTeam(t.agent))).toBe(true);
      const end = componentStates(all, all.length, repo, a, false);
      expect(Object.values(end)).not.toContain('issue');
      expect(Object.values(end)).not.toContain('fixed');
      expect(end[coreComponent(repo)]).toBe('clear');
    }
  });

  it('describes tool steps in plain words', () => {
    expect(plainStep({ tool: 'http.request', input: '', result: '', ms: 1, outcome: 'ok' })).toBe('Sent a test request');
    expect(plainStep({ tool: 'unknown.tool', input: '', result: '', ms: 1, outcome: 'ok' })).toBe('unknown.tool');
  });
});
