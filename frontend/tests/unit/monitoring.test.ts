import { describe, expect, it } from 'vitest';
import { monitoringSummary } from '@/lib/monitoring';

const base = {
  monitoringEnabled: true,
  eventsKnown: true,
  eventCount: 2,
  simulatedCount: 1,
  eventsTruncated: false,
  recommendationsKnown: true,
  recommendationCount: 1,
};

describe('monitoring summary', () => {
  it('keeps simulated events and simulation recommendations labelled', () => {
    const text = monitoringSummary(base);
    expect(text).toContain('2 recorded events');
    expect(text).toContain('1 labelled simulated');
    expect(text).toContain('not applied to a real system');
    expect(text).toContain('not the Defense Lab');
  });

  it('does not invent events or recommendations that have not loaded', () => {
    const text = monitoringSummary({
      ...base,
      eventsKnown: false,
      recommendationsKnown: false,
      eventCount: 9,
      recommendationCount: 9,
    });
    expect(text).toContain('have not loaded');
    expect(text).not.toContain('9');
  });

  it('says when monitoring is off and the feed is empty', () => {
    const text = monitoringSummary({
      ...base,
      monitoringEnabled: false,
      eventCount: 0,
      simulatedCount: 0,
      recommendationCount: 0,
    });
    expect(text).toContain('Monitoring is off');
    expect(text).toContain('No recorded events yet');
    expect(text).toContain('No simulation recommendation');
  });
});
