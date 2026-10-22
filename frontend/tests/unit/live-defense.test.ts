import { describe, expect, it } from 'vitest';
import {
  actionInWords,
  assertSingleSource,
  isOpenIncidentState,
  liveDefenseHref,
  liveDefenseMode,
  liveDefenseOverviewCopy,
  liveDefenseTab,
  MISSING_LIVE_APIS,
  rankQValues,
  USED_LIVE_APIS,
  withLiveDefenseMode,
} from '@/lib/live-defense';
import { PREVIEW_EVENTS, PREVIEW_INCIDENTS, PREVIEW_RECOMMENDATIONS } from '@/lib/live-defense-preview';

describe('live defense mode', () => {
  it('defaults to live and only enters layout-preview for the exact query value', () => {
    expect(liveDefenseMode(null)).toBe('live');
    expect(liveDefenseMode('1')).toBe('live');
    expect(liveDefenseMode('demo')).toBe('live');
    expect(liveDefenseMode('layout')).toBe('layout-preview');
  });

  it('toggles the preview flag without inventing other query params', () => {
    expect(withLiveDefenseMode('/projects/p1/live-defense', 'layout-preview')).toBe('/projects/p1/live-defense?preview=layout');
    expect(withLiveDefenseMode('/projects/p1/live-defense?preview=layout', 'live')).toBe('/projects/p1/live-defense');
  });

  it('builds console and standalone hrefs without mixing them', () => {
    expect(liveDefenseHref('prj_1', 'explain', 'live')).toBe('/projects/prj_1/live-defense/explain');
    expect(liveDefenseHref('prj_1', 'incidents', 'layout-preview')).toBe('/projects/prj_1/live-defense/incidents?preview=layout');
    expect(liveDefenseHref(null, 'overview')).toBe('/live-defense-pilot');
    expect(liveDefenseHref(null, 'explain')).toBe('/live-defense-pilot/explain');
  });

  it('classifies tabs for both console and standalone routes', () => {
    expect(liveDefenseTab('/projects/p1/live-defense')).toBe('overview');
    expect(liveDefenseTab('/projects/p1/live-defense/incidents/abc')).toBe('incidents');
    expect(liveDefenseTab('/live-defense-pilot/explain')).toBe('explain');
  });
});

describe('overview copy', () => {
  const base = {
    monitoringEnabled: true,
    eventsKnown: true,
    eventCount: 2,
    simulatedEventCount: 1,
    incidentsKnown: true,
    openIncidentCount: 1,
    simulatedIncidentCount: 1,
    recommendationsKnown: true,
    recommendationCount: 3,
  };

  it('labels simulated events and never claims a live map', () => {
    const text = liveDefenseOverviewCopy(base);
    expect(text).toContain('2 recorded events, 1 labelled simulated');
    expect(text).toContain('1 open incident, 1 labelled synthetic');
    expect(text).toContain('none is applied automatically');
    expect(text).toContain('does not draw a live map');
  });

  it('does not print counts that have not loaded', () => {
    const text = liveDefenseOverviewCopy({
      ...base,
      eventsKnown: false,
      incidentsKnown: false,
      recommendationsKnown: false,
      eventCount: 99,
      openIncidentCount: 99,
      recommendationCount: 99,
    });
    expect(text).toContain('have not loaded');
    expect(text).not.toContain('99');
  });
});

describe('Q ranking', () => {
  it('orders stored scores and keeps an empty list empty', () => {
    expect(rankQValues([])).toEqual([]);
    const ranked = rankQValues([
      { action: 'noop', node: null, q_value: 0.1 },
      { action: 'raise_monitoring', node: 'payments', q_value: 1.0 },
    ]);
    expect(ranked.map(item => item.action)).toEqual(['raise_monitoring', 'noop']);
    expect(ranked[0]?.rank).toBe(1);
    expect(ranked[0]?.bar).toBe(1);
    expect(ranked[1]?.bar).toBeCloseTo(0.1);
  });

  it('says recommended actions are not applied', () => {
    expect(actionInWords('isolate', 'api')).toContain('not applied');
    expect(actionInWords('rate_limit', 'api')).toContain('not applied');
    expect(actionInWords('raise_monitoring', 'payments')).toContain('payments');
  });
});

describe('source isolation', () => {
  it('refuses to mix live records with layout-preview samples', () => {
    expect(assertSingleSource([{ source: 'live' as const }, { source: 'live' as const }], 'events')).toBe('live');
    expect(() => assertSingleSource([{ source: 'live' as const }, { source: 'layout-preview' as const }], 'events')).toThrow(/refused to mix/);
  });

  it('keeps preview fixtures on the layout-preview source and non-control-plane ids', () => {
    expect(PREVIEW_EVENTS.every(item => item.source === 'layout-preview' && item.id.startsWith('layout-preview:'))).toBe(true);
    expect(PREVIEW_INCIDENTS.every(item => item.simulated && item.id.startsWith('layout-preview:'))).toBe(true);
    expect(PREVIEW_RECOMMENDATIONS[0]?.policy_version).toContain('not a checkpoint');
    expect(PREVIEW_RECOMMENDATIONS[0]?.caveat).toMatch(/not Q-values from a loaded policy/);
  });

  it('treats closed and rejected as not open', () => {
    expect(isOpenIncidentState('analysis')).toBe(true);
    expect(isOpenIncidentState('closed')).toBe(false);
    expect(isOpenIncidentState('rejected')).toBe(false);
  });

  it('documents existing endpoints and the ones still missing', () => {
    expect(USED_LIVE_APIS.some(item => item.path.includes('/defense-recommendations'))).toBe(true);
    expect(MISSING_LIVE_APIS.map(item => item.id)).toContain('component_health');
    expect(MISSING_LIVE_APIS.map(item => item.id)).toContain('live_inference');
  });
});
