import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { NodeGraph, isSettled } from '@/components/node-graph';
import type { LabNodeState, LabScenario } from '@/lib/lab-types';

const scenario: LabScenario = {
  name: 'demo', config_hash: 'x', split: 'eval', horizon: 10,
  nodes: [
    { name: 'web', criticality: 2, exposed: true, finding_severity: 1 },
    { name: 'db', criticality: 5, exposed: false, finding_severity: 0 },
  ],
  edges: [['web', 'db']],
};
const states: LabNodeState[] = [
  { node: 'web', alert_rate: 0.25, anomaly_score: 0.5, monitoring_level: 1, rate_limited: false, isolated: false, reassessment_pending: false, hidden_stage_ground_truth: 'none' },
  { node: 'db', alert_rate: 0.75, anomaly_score: 0.9, monitoring_level: 2, rate_limited: false, isolated: true, reassessment_pending: false, hidden_stage_ground_truth: 'none' },
];

beforeEach(() => {
  vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({ matches: false }));
  vi.stubGlobal('requestAnimationFrame', vi.fn().mockReturnValue(1));
  vi.stubGlobal('cancelAnimationFrame', vi.fn());
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('does not trap vertical touch scrolling and keeps the topology test id', () => {
  render(<NodeGraph scenario={scenario} states={states} />);
  const svg = screen.getByTestId('topology');
  expect(svg.style.touchAction).toBe('pan-y');
  expect(svg.getAttribute('class')).not.toContain('touch-none');
});

it('exposes every node value to assistive tech in a table', () => {
  render(<NodeGraph scenario={scenario} states={states} />);
  const row = screen.getByRole('row', { name: /^db/ });
  const cells = within(row).getAllByRole('cell').map(c => c.textContent);
  expect(cells).toContain('0.90');
  expect(cells).toContain('0.75');
  expect(cells).toContain('2');
  expect(cells.at(-1)).toContain('isolated');
});

it('makes nodes focusable and shows the detail card on focus', () => {
  render(<NodeGraph scenario={scenario} states={states} />);
  const node = screen.getByRole('img', { name: /^db: criticality 5/ });
  expect(node.getAttribute('tabindex')).toBe('0');
  fireEvent.focus(node);
  expect(screen.getAllByText('anomaly score').length).toBeGreaterThan(0);
  fireEvent.blur(node);
  expect(screen.queryByText('anomaly score')).toBeNull();
});

it('reports a simulation as settled only when free bodies are slow', () => {
  expect(isSettled([{ vx: 0.001, vy: 0, pinned: false }])).toBe(true);
  expect(isSettled([{ vx: 0.5, vy: 0, pinned: false }])).toBe(false);
  expect(isSettled([{ vx: 5, vy: 5, pinned: true }])).toBe(true);
});
