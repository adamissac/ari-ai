import { describe, expect, it } from 'vitest';
import { bucketCounts, findingBucket, findingGroup } from '@/lib/findings';
import { projectOverview } from '@/lib/overview';
import { pillarLoop } from '@/lib/pillars';

const loop = (over: Partial<Parameters<typeof pillarLoop>[0]> = {}) => pillarLoop({
  projectId: 'prj_1', repoCount: 1, activeScopeCount: 1, assessmentCount: 1, findings: [],
  monitoringEnabled: true, monitoringEventCount: 0, reassessmentCount: 0, ...over,
});
const ov = (over: Partial<Parameters<typeof projectOverview>[0]> = {}) => projectOverview({
  projectId: 'prj_1', repoCount: 1, activeScopeCount: 1, monitoringEnabled: true,
  assessments: [{ id: 'a', state: 'COMPLETED', created_at: '2026-10-17T00:00:00Z' }], findings: [], ...over,
});

describe('one finding classifier', () => {
  it('buckets derive from findingGroup', () => {
    expect(findingBucket('hypothesis')).toBe('untested');
    expect(findingBucket('inconclusive')).toBe('inconclusive');
    for (const s of ['refuted', 'closed', 'accepted_risk']) { expect(findingGroup(s)).toBe('closed'); expect(findingBucket(s)).toBe('dismissed'); }
    for (const s of ['verified', 'hardened']) expect(findingBucket(s)).toBe('fixed');
    for (const s of ['validated', 'diagnosed', 'patch_proposed', 'patch_rejected', 'unresolved', 'needs_recheck']) expect(findingBucket(s)).toBe('confirmed');
  });
  it('overview and pillars give the same counts for the same findings', () => {
    const findings = [
      { kind: 'security', status: 'validated' }, { kind: 'security', status: 'inconclusive' }, { kind: 'security', status: 'hypothesis' },
      { kind: 'security', status: 'closed' }, { kind: 'functional', status: 'patch_rejected' }, { kind: 'functional', status: 'verified' },
    ];
    expect(bucketCounts(findings, 'security')).toMatchObject({ confirmed: 1, inconclusive: 1, untested: 1, dismissed: 1 });
    const o = ov({ findings });
    expect([o.securityOpen, o.codeOpen, o.untested, o.inconclusive, o.verifiedFixes]).toEqual([1, 1, 1, 1, 1]);
    const nodes = loop({ findings });
    expect(nodes[1]?.status).toBe('1 behaviour problem still open.');
    expect(nodes[2]?.status).toBe('1 confirmed weakness, 1 untested suspicion, 1 inconclusive test result.');
  });
  it('inconclusive and hypotheses are never "no problems"', () => {
    expect(loop({ findings: [{ kind: 'security', status: 'inconclusive' }] })[2]?.status).toBe('1 inconclusive test result.');
    expect(loop({ findings: [{ kind: 'security', status: 'hypothesis' }] })[2]?.status).toBe('1 untested suspicion.');
    expect(loop({ findings: [{ kind: 'functional', status: 'hypothesis' }] })[1]?.status).toBe('1 untested suspicion.');
    const o = ov({ findings: [{ kind: 'security', status: 'hypothesis' }, { kind: 'security', status: 'inconclusive' }] });
    expect(o.headline).toBe('The latest check finished. No confirmed open findings, but 1 untested suspicion and 1 inconclusive test result remain.');
  });
});

describe('scopes still loading', () => {
  it('pillars: null scope count is unknown, not "blocked until a person approves"', () => {
    const attack = loop({ activeScopeCount: null })[2];
    expect(attack?.status).toBe('Scopes did not load.');
    expect(attack?.tone).toBe('unknown');
    expect(attack?.status).not.toMatch(/Blocked/);
  });
  it('overview: null scope count does not claim no environment is approved', () => {
    const o = ov({ activeScopeCount: null });
    expect(o.headline).toMatch(/Scopes did not load/);
    expect(o.headline).not.toMatch(/No safe test environment/);
  });
});
