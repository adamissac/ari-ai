import { describe, expect, it } from 'vitest';
import { outcomeViews } from '@/components/commit-assessment-chips';
import { commitOutcome, foundSomething, OPEN_REASON } from '@/lib/findings';

const f = (assessment_id: string, status: string) => ({ assessment_id, status });

describe('commit outcome', () => {
  it('counts only the given run and splits proven, fixed and unproven', () => {
    const items = [f('a', 'validated'), f('a', 'patch_proposed'), f('a', 'verified'), f('a', 'hypothesis'), f('a', 'inconclusive'), f('a', 'refuted'), f('b', 'validated')];
    const o = commitOutcome(items, 'a');
    expect(o).toEqual({ needsFix: 2, fixed: 1, unproven: 2 });
    expect(foundSomething(o)).toBe(true);
    expect(outcomeViews(o).map(v => v.label)).toEqual(['2 need a fix', '1 fixed']);
  });

  it('a run with only suspicions or nothing reads as no issues', () => {
    const suspicions = commitOutcome([f('a', 'hypothesis')], 'a');
    expect(foundSomething(suspicions)).toBe(false);
    expect(outcomeViews(suspicions).map(v => v.label)).toEqual(['No proven issues']);
    expect(outcomeViews(commitOutcome([], 'a')).map(v => v.label)).toEqual(['No issues found']);
    expect(outcomeViews({ needsFix: 1, fixed: 0, unproven: 0 })[0]?.label).toBe('1 needs a fix');
  });

  it('every open-but-proven status has a plain reason', () => {
    for (const s of ['validated', 'diagnosed', 'patch_proposed', 'patch_rejected', 'unresolved', 'needs_recheck']) expect(OPEN_REASON[s]).toBeTruthy();
  });
});
