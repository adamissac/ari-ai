import { describe, expect, it } from 'vitest';
import { assessmentPhases, EVENT_LOG_MAX_PAGES, EVENT_LOG_PAGE_NOTE, fullEventLog } from '@/lib/journey';

describe('assessment phases', () => {
  it('uses the event log and leaves monitoring off this page', () => {
    const phases = assessmentPhases({
      state: 'VALIDATION',
      events: [
        { type: 'assessment.state_changed', state: 'INDEXING', message: 'state -> INDEXING' },
        { type: 'assessment.state_changed', state: 'FUNCTIONAL_REVIEW', message: 'state -> FUNCTIONAL_REVIEW' },
        { type: 'assessment.state_changed', state: 'RECON', message: 'state -> RECON' },
        { type: 'assessment.state_changed', state: 'VALIDATION', message: 'state -> VALIDATION' },
      ],
      findingStatuses: ['hypothesis'],
    });
    const byId = Object.fromEntries(phases.map(stage => [stage.id, stage.status]));
    expect(byId.understand).toBe('completed');
    expect(byId.review).toBe('completed');
    expect(byId.security).toBe('running');
    expect(byId.verify).toBe('not_started');
    expect(byId.monitor).toBeUndefined();
  });

  it('does not mark phases skipped when the log failed to load', () => {
    const phases = assessmentPhases({ state: 'COMPLETED', events: null, findingStatuses: [] });
    expect(phases.find(stage => stage.id === 'understand')?.detail).toMatch(/event log did not load/);
  });

  it('verification still requires a finding verdict', () => {
    const phases = assessmentPhases({
      state: 'COMPLETED',
      events: [
        { type: 'assessment.state_changed', state: 'REMEDIATION', message: 'state -> REMEDIATION' },
        { type: 'assessment.state_changed', state: 'COMPLETED', message: 'state -> COMPLETED' },
      ],
      findingStatuses: ['verified'],
    });
    expect(phases.find(stage => stage.id === 'verify')?.status).toBe('completed');
    expect(phases.find(stage => stage.id === 'verify')?.detail).toMatch(/not a claim about the whole application/);
  });

  it('follows next_cursor until the log ends', async () => {
    const pages: Record<number, { items: number[]; next_cursor: string | null }> = {
      0: { items: [1, 2, 3], next_cursor: '3' },
      3: { items: [4, 5, 6], next_cursor: '6' },
      6: { items: [7], next_cursor: null },
    };
    const calls: number[] = [];
    const log = await fullEventLog(async after => { calls.push(after); return pages[after]!; });
    expect(calls).toEqual([0, 3, 6]);
    expect(log).toEqual({ items: [1, 2, 3, 4, 5, 6, 7], truncated: false });
  });

  it('stops at the page cap and reports the log as truncated', async () => {
    let calls = 0;
    const log = await fullEventLog(async after => { calls++; return { items: [after + 1], next_cursor: String(after + 1) }; });
    expect(calls).toBe(EVENT_LOG_MAX_PAGES);
    expect(log.items).toHaveLength(EVENT_LOG_MAX_PAGES);
    expect(log.truncated).toBe(true);
  });

  it('stops on a cursor that does not move forward', async () => {
    let calls = 0;
    const log = await fullEventLog(async () => { calls++; return { items: [1], next_cursor: '0' }; });
    expect(calls).toBe(1);
    expect(log.truncated).toBe(true);
  });

  it('keeps the honesty note stable for a truncated log', () => {
    expect(EVENT_LOG_PAGE_NOTE).toContain('first 10,000 events');
    expect(EVENT_LOG_PAGE_NOTE).toContain('later phase unmarked');
    const phases = assessmentPhases({
      state: 'COMPLETED',
      events: [
        { type: 'assessment.state_changed', state: 'INDEXING', message: 'state -> INDEXING' },
        { type: 'assessment.state_changed', state: 'COMPLETED', message: 'state -> COMPLETED' },
      ],
      findingStatuses: [],
      eventLogTruncated: true,
    });
    expect(phases.find(stage => stage.id === 'repair')?.detail).toMatch(/first 10,000 events/);
  });
});
