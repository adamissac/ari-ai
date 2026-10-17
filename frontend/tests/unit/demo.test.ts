import { describe, expect, it } from 'vitest';
import { layoutLayers } from '@/components/defense-map';
import { observedState } from '@/components/lab-command';
import { DEMO_ORGS, DEMO_REPOS, demoSha, findCommit, relativeTime, reposFor } from '@/lib/demo/data';
import { AGENT_ORDER, analyze, previousVersion, replaySteps } from '@/lib/demo/scenarios';

describe('simulated demo data', () => {
  it('gives every org at least one repository and every repository recent commits', () => {
    for (const org of DEMO_ORGS) expect(reposFor(org.login).length).toBeGreaterThan(0);
    for (const repo of DEMO_REPOS) {
      expect(repo.commits.length).toBeGreaterThan(0);
      const ages = repo.commits.map(c => c.minutesAgo);
      expect(ages).toEqual([...ages].sort((a, b) => a - b));
    }
  });

  it('uses stable, unique 40-hex commit SHAs that resolve by prefix', () => {
    expect(demoSha('x')).toBe(demoSha('x'));
    expect(demoSha('x')).toMatch(/^[0-9a-f]{40}$/);
    const shas = DEMO_REPOS.flatMap(r => r.commits.map(c => c.sha));
    expect(new Set(shas).size).toBe(shas.length);
    const repo = DEMO_REPOS[0]!;
    expect(findCommit(repo, repo.commits[1]!.sha.slice(0, 7))).toBe(repo.commits[1]);
  });

  it('formats commit ages like a commit list', () => {
    expect(relativeTime(14)).toBe('14 min ago');
    expect(relativeTime(95)).toBe('2 hours ago');
    expect(relativeTime(2890)).toBe('2 days ago');
  });

  it('derives a plausible previous release for dependency diffs', () => {
    expect(previousVersion('2.12.4')).toBe('2.12.3');
    expect(previousVersion('1.47')).toBe('1.46');
    expect(previousVersion('5.0')).toBe('4.9');
  });
});

describe('simulated commit analysis', () => {
  const all = DEMO_REPOS.flatMap(repo => repo.commits.map(commit => ({ repo, commit, analysis: analyze(repo, commit) })));

  it('always lists the seven agents in orchestrator order', () => {
    for (const { analysis } of all) expect(analysis.agents.map(a => a.agent)).toEqual(AGENT_ORDER.map(a => a.agent));
  });

  it('matches the commit verdict: fixed commits carry a finding and an accepted Verify', () => {
    for (const { commit, analysis } of all) {
      const verify = analysis.agents.find(a => a.agent === 'verify')!;
      if (commit.verdict === 'fixed') {
        expect(analysis.findings.length).toBeGreaterThan(0);
        expect(verify.outcome).toMatch(/^Accepted/);
      }
      if (commit.verdict === 'clean') {
        expect(analysis.findings).toEqual([]);
        expect(analysis.patch).toBeNull();
      }
      if (commit.verdict === 'needs_review') expect(verify.outcome).toMatch(/^Not accepted/);
    }
  });

  it('keeps skipped agents free of tool calls and denials visible on the others', () => {
    for (const { analysis } of all) {
      for (const agent of analysis.agents) if (agent.status === 'skipped') expect(agent.steps).toEqual([]);
    }
    const authz = all.find(x => x.commit.scenario === 'authz')!.analysis;
    expect(authz.agents.flatMap(a => a.steps).some(s => s.outcome === 'denied')).toBe(true);
    expect(replaySteps(authz).length).toBe(authz.agents.reduce((n, a) => n + a.steps.length, 0));
  });

  it('only refers to components the repository has', () => {
    for (const { repo, analysis } of all) {
      const ids = new Set(repo.components.map(c => c.id));
      for (const id of Object.keys(analysis.defense.watch)) expect(ids.has(id)).toBe(true);
    }
  });
});

describe('defense map', () => {
  it('lays components out left to right by dependency distance', () => {
    const pos = layoutLayers(
      [{ id: 'edge', label: 'Edge', kind: 'edge', critical: false }, { id: 'api', label: 'API', kind: 'service', critical: true }, { id: 'db', label: 'DB', kind: 'data', critical: true }],
      [['edge', 'api'], ['api', 'db']],
    );
    expect(pos.get('edge')!.x).toBeLessThan(pos.get('api')!.x);
    expect(pos.get('api')!.x).toBeLessThan(pos.get('db')!.x);
  });

  it('maps a recorded lab step to observed states only', () => {
    const base = { node: 'api', alert_rate: 0, anomaly_score: 0, monitoring_level: 0, rate_limited: false, isolated: false, reassessment_pending: false, hidden_stage_ground_truth: 'impact' as const };
    expect(observedState(base)).toBe('healthy');
    expect(observedState({ ...base, rate_limited: true })).toBe('limited');
    expect(observedState({ ...base, isolated: true, rate_limited: true })).toBe('isolated');
    expect(observedState({ ...base, monitoring_level: 1 })).toBe('checking');
    expect(observedState({ ...base, anomaly_score: 0.8 })).toBe('attention');
  });
});
