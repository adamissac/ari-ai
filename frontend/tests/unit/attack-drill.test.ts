import { describe, expect, it } from 'vitest';
import { parseDrillResult } from '@/lib/attack-drill';

const ok = {
  simulated: true,
  repo: 'acme/shop',
  plan_author: 'claude',
  plan: { route: 'GET /invoices/{id}', technique: 'enumeration', attacker: 'Insider', objective: 'Read others', narrative: 'Walks IDs.', steps: ['a', 'b'] },
  detection: { detected: true, anomaly_score: 1, reasons: ['rate z=11'], monitoring_event_ids: ['evt_1'], linked_findings: [] },
  response: { responder: 'rule-based', executed: false, actions: [{ action: 'Rate-limit', detail: 'Throttle' }] },
};

describe('parseDrillResult', () => {
  it('accepts a simulated drill result', () => {
    const r = parseDrillResult(ok);
    expect(r?.plan.route).toBe('GET /invoices/{id}');
    expect(r?.detection.anomalyScore).toBe(1);
    expect(r?.response.actions).toHaveLength(1);
  });

  it('rejects anything not labelled simulated, or claiming execution', () => {
    expect(parseDrillResult({ ...ok, simulated: false })).toBeNull();
    expect(parseDrillResult({ ...ok, response: { ...ok.response, executed: true } })).toBeNull();
    expect(parseDrillResult({ ...ok, plan_author: 'someone' })).toBeNull();
    expect(parseDrillResult(null)).toBeNull();
  });
});
