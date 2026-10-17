import { describe, expect, it } from 'vitest';
import { assessmentPhases, EVENT_LOG_PAGE_NOTE, eventLogPageTruncated } from '@/lib/journey';

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

  it('treats a full first page as truncated and keeps the honesty note stable', () => {
    expect(eventLogPageTruncated(499)).toBe(false);
    expect(eventLogPageTruncated(500)).toBe(true);
    expect(EVENT_LOG_PAGE_NOTE).toContain('first 500 events');
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
    expect(phases.find(stage => stage.id === 'repair')?.detail).toMatch(/first 500 events/);
  });
});
