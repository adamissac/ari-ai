import { describe, expect, it } from 'vitest';
import { afterSide, beforeSide, splitRows } from '@/lib/before-after';
import { parseUnifiedDiff } from '@/lib/diff';
import { GLOSSARY } from '@/lib/glossary';
import { actionInWords, episodeOutcome, episodeTimeline, policyName, SCORE_METRICS, scoreboard } from '@/lib/lab-plain';
import type { DefenseLabBundle, LabEpisode } from '@/lib/lab-types';
import { pillarLoop } from '@/lib/pillars';
import { agentRelay, type RelayTile } from '@/lib/relay';

const loop = (over: Partial<Parameters<typeof pillarLoop>[0]> = {}) => pillarLoop({
  projectId: 'prj_1', repoCount: 1, activeScopeCount: 1, assessmentCount: 1, findings: [],
  monitoringEnabled: true, monitoringEventCount: 0, reassessmentCount: 0, ...over,
});

describe('pillar loop', () => {
  it('is five connected steps across the three pillars, in order', () => {
    expect(loop().map(n => n.id)).toEqual(['understand', 'review', 'attack', 'prove', 'monitor']);
    expect(loop().map(n => n.pillar)).toEqual(['Shared intelligence', 'Pillar 1', 'Pillar 2', 'Pillar 2', 'Pillar 3']);
  });
  it('counts only from records and separates confirmed weaknesses from untested suspicions', () => {
    const nodes = loop({ findings: [
      { kind: 'functional', status: 'validated' }, { kind: 'security', status: 'hypothesis' },
      { kind: 'security', status: 'validated' }, { kind: 'security', status: 'verified' }, { kind: 'security', status: 'refuted' },
    ] });
    expect(nodes[1]?.status).toBe('1 behaviour problem still open.');
    expect(nodes[2]?.status).toBe('1 confirmed weakness, 1 untested suspicion.');
    expect(nodes[3]?.status).toMatch(/^1 fix accepted by independent tests\. Proposed only; nothing was merged or deployed\.$/);
  });
  it('a count that did not load is never shown as zero', () => {
    const nodes = loop({ findings: null, monitoringEventCount: null });
    expect(nodes[1]?.status).toBe('Findings did not load.');
    expect(nodes[1]?.tone).toBe('unknown');
    expect(nodes[4]?.status).toBe('Monitoring events did not load.');
  });
  it('security testing is blocked, and links to scopes, until a scope is approved', () => {
    const attack = loop({ activeScopeCount: 0 })[2];
    expect(attack?.status).toMatch(/Blocked/);
    expect(attack?.href).toBe('/projects/prj_1/scopes');
  });
  it('nothing is called checked before an assessment exists', () => {
    expect(loop({ assessmentCount: 0 })[1]?.status).toBe('Not checked yet.');
  });
});

const run = (agent: string, status = 'succeeded') => ({ agent: agent as RelayTile['agent'], status, tool_calls: [] });

describe('agent relay', () => {
  it('lists the eight agents in order with the human gate before Patch', () => {
    const items = agentRelay({ runs: [], findings: [], state: 'CREATED' });
    expect(items.map(i => (i.kind === 'gate' ? 'GATE' : i.agent))).toEqual(['reviewer', 'scout', 'probe', 'trace', 'diagnose', 'GATE', 'patch', 'verify', 'fortify']);
    expect(items.filter(i => i.kind === 'agent').every(i => i.kind === 'agent' && i.status === 'not_run' && i.handoff === 'Nothing handed on yet.')).toBe(true);
  });
  it('waits at the gate while the run awaits approval and never marks later agents done early', () => {
    const items = agentRelay({ runs: ['reviewer', 'scout', 'probe', 'trace', 'diagnose'].map(a => run(a)), findings: [], state: 'AWAITING_APPROVAL' });
    const gate = items.find(i => i.kind === 'gate');
    expect(gate?.kind === 'gate' && gate.status).toBe('waiting');
    const patch = items.find(i => i.kind === 'agent' && i.agent === 'patch');
    expect(patch?.kind === 'agent' && patch.status).toBe('not_run');
  });
  it('handoffs are counted from the findings that exist', () => {
    const findings = [{ kind: 'functional', status: 'verified' }, { kind: 'security', status: 'hardened' }, { kind: 'security', status: 'refuted' }];
    const items = agentRelay({ runs: ['reviewer', 'scout', 'probe', 'verify'].map(a => run(a)), findings, state: 'COMPLETED' });
    const text = (a: string) => { const t = items.find(i => i.kind === 'agent' && i.agent === a); return t?.kind === 'agent' ? t.handoff : ''; };
    expect(text('reviewer')).toBe('Recorded 1 behaviour problem.');
    expect(text('scout')).toBe('Passed 2 suspicions to Probe.');
    expect(text('probe')).toBe('Test results: 1 confirmed, 1 ruled out. Each finding shows its recorded test.');
    expect(text('verify')).toBe('2 fixes accepted.');
  });
  it('a failed agent hands nothing on; a declined approval is shown as no fix built', () => {
    const items = agentRelay({ runs: [run('reviewer'), run('scout', 'failed'), run('diagnose')], findings: [], state: 'COMPLETED' });
    const scout = items.find(i => i.kind === 'agent' && i.agent === 'scout');
    expect(scout?.kind === 'agent' && scout.handoff).toBe('Stopped with an error, so nothing was handed on.');
    const gate = items.find(i => i.kind === 'gate');
    expect(gate?.kind === 'gate' && gate.status).toBe('not_used');
  });
});

describe('before / after', () => {
  it('before reflects only the recorded validation', () => {
    expect(beforeSide({ kind: 'security', status: 'validated', validation: 'confirmed' }).headline).toBe('The problem was reproduced');
    expect(beforeSide({ kind: 'security', status: 'hypothesis', validation: null }).headline).toBe('No reproduction recorded');
    expect(beforeSide({ kind: 'functional', status: 'verified', validation: null }).headline).toBe('A test showed the wrong behaviour');
  });
  it('an unverified or rejected patch is never presented as a fix', () => {
    expect(afterSide(null, false).side.headline).toBe('No fix proposed');
    expect(afterSide(null, true).side.detail).toMatch(/does not count as a fix yet/);
    const rejected = afterSide({ verdict: 'rejected', checks: [{ name: 'functional_suite_passes', passed: false }] }, true);
    expect(rejected.side.tone).toBe('bad');
    expect(rejected.side.detail).toMatch(/A rejected patch is not a fix/);
  });
  it('accepted checks are translated to plain words and say nothing was deployed', () => {
    const ok = afterSide({ verdict: 'accepted', checks: [{ name: 'original_check_now_fails_to_reproduce', passed: true }, { name: 'functional_suite_passes', passed: true }] }, true);
    expect(ok.checks.map(c => c.label)).toEqual(['The original problem no longer happens', 'The normal tests still pass']);
    expect(ok.side.detail).toMatch(/2 of 2 checks passed.*not merged or deployed/);
  });
  it('split rows pair removed and added lines and keep context on both sides', () => {
    const [file] = parseUnifiedDiff('--- a/x.py\n+++ b/x.py\n@@ -1,3 +1,4 @@\n a\n-b\n+B\n+C\n d\n');
    const rows = splitRows(file!);
    expect(rows[0]?.hunk).toBeDefined();
    expect(rows[1]).toEqual({ left: { no: 1, text: 'a', kind: 'context' }, right: { no: 1, text: 'a', kind: 'context' } });
    expect(rows[2]).toEqual({ left: { no: 2, text: 'b', kind: 'del' }, right: { no: 2, text: 'B', kind: 'add' } });
    expect(rows[3]).toEqual({ left: null, right: { no: 3, text: 'C', kind: 'add' } });
    expect(rows[4]?.left?.no).toBe(3);
  });
});

const ci = (mean: number | null, lo: number | null, hi: number | null) => ({ mean, ci95: [lo, hi] as [number | null, number | null] });
const bundle = {
  metrics: [
    { policy: 'ddqn', pooled: { compromise_rate: ci(0.071, 0.05, 0.09), service_uptime: ci(0.944, 0.94, 0.95), false_disruption_rate: ci(0.75, 0.7, 0.8) }, per_scenario: {} },
    { policy: 'noop', pooled: { compromise_rate: ci(1, 1, 1), service_uptime: ci(1, 1, 1), false_disruption_rate: ci(null, null, null) }, per_scenario: {} },
  ],
} as unknown as DefenseLabBundle;

describe('Defense Lab in plain words', () => {
  it('scores are the bundle values as percentages, with the best marked', () => {
    const compromise = scoreboard(bundle, SCORE_METRICS.find(m => m.key === 'compromise_rate')!);
    expect(compromise[0]?.value).toBeCloseTo(7.1);
    expect(compromise[0]?.lo).toBeCloseTo(5);
    expect(compromise.map(c => c.best)).toEqual([true, false]);
    const uptime = scoreboard(bundle, SCORE_METRICS.find(m => m.key === 'service_uptime')!);
    expect(uptime.map(c => c.best)).toEqual([false, true]);
    const fd = scoreboard(bundle, SCORE_METRICS.find(m => m.key === 'false_disruption_rate')!);
    expect(fd[1]?.value).toBeNull();
  });
  it('policies and actions have plain names, unknown ones stay raw', () => {
    expect(policyName('ddqn')).toBe('Trained AI defender');
    expect(policyName('mystery')).toBe('mystery');
    expect(actionInWords('isolate:db')).toBe('Cut db off from the network');
    expect(actionInWords('noop')).toBe('Waited and watched');
    expect(actionInWords('weird:x')).toBe('weird:x');
  });
  it('timeline takes the furthest hidden stage per step and marks defender actions', () => {
    const node = (stage: string) => ({ node: 'n', alert_rate: 0, anomaly_score: 0, monitoring_level: 0, rate_limited: false, isolated: false, reassessment_pending: false, hidden_stage_ground_truth: stage });
    const ep = { policy: 'ddqn', scenario: 's', episode_seed: 1, training_seed: 0, total_return: 0, compromised: false, impact_nodes: [], steps: [
      { t: 0, action: 'noop', reward: 0, reward_components: {}, nodes: [node('none'), node('foothold')] },
      { t: 1, action: 'isolate:api', reward: 0, reward_components: {}, nodes: [node('escalated'), node('none')] },
    ] } as unknown as LabEpisode;
    expect(episodeTimeline(ep)).toEqual([{ stage: 'foothold', acted: false, disruptive: false }, { stage: 'escalated', acted: true, disruptive: true }]);
    expect(episodeOutcome(ep)).toBe('Trained AI defender: the simulated attacker never reached its goal. The defender acted 1 time in 2 steps.');
  });
});

describe('glossary', () => {
  it('defines every term used by the clarity components', () => {
    for (const t of ['finding', 'scope', 'sandbox', 'patch', 'verification', 'monitoring', 'simulation'] as const) expect(GLOSSARY[t].length).toBeGreaterThan(20);
  });
});
