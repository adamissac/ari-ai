import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { layoutNetwork, NodeGraph, INTERNET_ID } from '@/components/node-graph';
import type { LabNodeState, LabScenario } from '@/lib/lab-types';

const scenario: LabScenario = {
  name: 'demo', config_hash: 'x', split: 'eval', horizon: 10,
  nodes: [
    { name: 'gateway', criticality: 0.3, exposed: true, finding_severity: 0.3 },
    { name: 'api', criticality: 0.5, exposed: true, finding_severity: 0.5 },
    { name: 'db', criticality: 1, exposed: false, finding_severity: 0.1 },
  ],
  edges: [['gateway', 'api'], ['api', 'db']],
};
const states: LabNodeState[] = [
  { node: 'gateway', alert_rate: 0.1, anomaly_score: 0.05, monitoring_level: 0, rate_limited: false, isolated: false, reassessment_pending: false, hidden_stage_ground_truth: 'none' },
  { node: 'api', alert_rate: 0.25, anomaly_score: 0.5, monitoring_level: 1, rate_limited: true, isolated: false, reassessment_pending: false, hidden_stage_ground_truth: 'foothold' },
  { node: 'db', alert_rate: 0.75, anomaly_score: 0.9, monitoring_level: 1, rate_limited: false, isolated: true, reassessment_pending: true, hidden_stage_ground_truth: 'none' },
];

beforeEach(() => {
  vi.stubGlobal('requestAnimationFrame', vi.fn().mockReturnValue(1));
  vi.stubGlobal('cancelAnimationFrame', vi.fn());
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('does not trap vertical touch scrolling and keeps the topology test id', () => {
  render(<NodeGraph scenario={scenario} states={states} />);
  const svg = screen.getByTestId('topology');
  expect(svg.style.touchAction).toBe('pan-y');
});

it('lays the network out in stable columns from the internet inwards', () => {
  const a = layoutNetwork(scenario);
  const b = layoutNetwork(scenario);
  expect([...a.entries()]).toEqual([...b.entries()]); // deterministic: no drift between renders
  expect(a.get(INTERNET_ID)!.x).toBeLessThan(a.get('gateway')!.x);
  expect(a.get('gateway')!.x).toBe(a.get('api')!.x); // both internet-exposed → same column
  expect(a.get('db')!.x).toBeGreaterThan(a.get('api')!.x);
});

it('exposes every node value to assistive tech in a table', () => {
  render(<NodeGraph scenario={scenario} states={states} />);
  const row = screen.getByRole('row', { name: /^db/ });
  const cells = within(row).getAllByRole('cell').map(c => c.textContent);
  expect(cells).toContain('0.90');
  expect(cells).toContain('0.75');
  expect(cells).toContain('1');
  expect(cells.at(-1)).toContain('isolated');
});

it('names each service in plain words with its observed state', () => {
  render(<NodeGraph scenario={scenario} states={states} />);
  const db = screen.getByRole('button', { name: /^Database \(db\), critical: Suspicious activity · cut off · watched closely · re-check requested/ });
  expect(db.getAttribute('data-signal')).toBe('high');
  expect(db.getAttribute('data-isolated')).toBe('true');
  const api = screen.getByRole('button', { name: /^API server \(api\), internet-exposed: Elevated activity · traffic slowed · watched closely/ });
  expect(api.getAttribute('data-signal')).toBe('elevated');
  expect(screen.getByRole('button', { name: /^Gateway/ }).getAttribute('data-signal')).toBe('quiet');
});

it('selects with click and keyboard, and moves between services with arrow keys', () => {
  const onSelect = vi.fn();
  render(<NodeGraph scenario={scenario} states={states} onSelect={onSelect} />);
  const gateway = screen.getByRole('button', { name: /^Gateway/ });
  expect(gateway.getAttribute('tabindex')).toBe('0');
  fireEvent.pointerDown(gateway, { button: 0 });
  fireEvent.pointerUp(gateway);
  expect(onSelect).toHaveBeenLastCalledWith('gateway');
  fireEvent.keyDown(gateway, { key: 'Enter' });
  expect(onSelect).toHaveBeenLastCalledWith('gateway');
  fireEvent.keyDown(gateway, { key: 'ArrowRight' });
  expect(onSelect).toHaveBeenLastCalledWith('api');
  fireEvent.keyDown(gateway, { key: 'Escape' });
  expect(onSelect).toHaveBeenLastCalledWith(null);
});

it('shows a summary on focus and hides it on blur', () => {
  render(<NodeGraph scenario={scenario} states={states} />);
  const db = screen.getByRole('button', { name: /^Database/ });
  fireEvent.focus(db);
  expect(screen.getAllByText('Suspicious activity · cut off · watched closely · re-check requested').length).toBeGreaterThan(0);
  fireEvent.blur(db);
  expect(document.querySelector('.net-tip')).toBeNull();
});

it('hides the attacker ground truth unless the overlay is on, and labels it when shown', () => {
  const { rerender } = render(<NodeGraph scenario={scenario} states={states} />);
  expect(screen.queryByText(/attacker: foothold/)).toBeNull();
  rerender(<NodeGraph scenario={scenario} states={states} showTruth />);
  expect(screen.getByText('attacker: foothold')).toBeTruthy();
  expect(screen.getByRole('note').textContent).toContain('the defender cannot see this');
});

it('highlights the acted-on service only when the step has a real action', () => {
  const { rerender } = render(<NodeGraph scenario={scenario} states={states} action="noop" />);
  expect(document.querySelector('.net-act')).toBeNull();
  rerender(<NodeGraph scenario={scenario} states={states} action="isolate:db" t={3} />);
  expect(document.querySelector('[data-node="db"] .net-act')).not.toBeNull();
});
