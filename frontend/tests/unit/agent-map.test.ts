import { describe, expect, it } from 'vitest';
import { affected, componentStates, coreComponent, plainStep, stepComponent, ticks } from '@/lib/demo/agent-map';
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

  it('describes tool steps in plain words', () => {
    expect(plainStep({ tool: 'http.request', input: '', result: '', ms: 1, outcome: 'ok' })).toBe('Sent a test request');
    expect(plainStep({ tool: 'unknown.tool', input: '', result: '', ms: 1, outcome: 'ok' })).toBe('unknown.tool');
  });
});
