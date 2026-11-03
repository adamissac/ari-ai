import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import type { AgentName } from '@hackatl/frontend-transport';
import { afterEach, expect, it, vi } from 'vitest';
import { AgentRelay } from '@/components/agent-relay';
import { agentRelay, type FindingFacts } from '@/lib/relay';

afterEach(cleanup);

const findings: FindingFacts[] = [
  { kind: 'functional', status: 'hypothesis' },
  { kind: 'functional', status: 'validated' },
  { kind: 'security', status: 'hypothesis' },
  { kind: 'security', status: 'validated' },
  { kind: 'security', status: 'verified' },
  { kind: 'security', status: 'hardened' },
];

const run = (agent: AgentName) => ({ agent, status: 'succeeded', tool_calls: [] });
const items = () => agentRelay({
  runs: [run('reviewer'), run('scout')],
  findings,
  state: 'COMPLETED',
  approvals: [],
  skipNote: 'no confirmed findings',
});

function renderRelay(selected: AgentName = 'reviewer', onSelect = vi.fn()) {
  render(<AgentRelay items={items()} findings={findings} selected={selected} onSelect={onSelect} skipNote="no confirmed findings" />);
  return screen.getByTestId('agent-relay');
}

it('renders all eight agent rows in order with the approval gate between Diagnose and Patch', () => {
  const section = renderRelay();
  expect([...section.querySelectorAll('button[data-testid^="relay-"]')].map(row => row.getAttribute('data-testid'))).toEqual([
    'relay-reviewer',
    'relay-scout',
    'relay-probe',
    'relay-trace',
    'relay-diagnose',
    'relay-patch',
    'relay-verify',
    'relay-fortify',
  ]);

  const diagnose = screen.getByTestId('relay-diagnose');
  const gate = screen.getByTestId('relay-gate');
  const patch = screen.getByTestId('relay-patch');
  expect(diagnose.compareDocumentPosition(gate) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(gate.compareDocumentPosition(patch) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});

it('shows the early-end reason once instead of repeating it in idle rows', () => {
  const section = renderRelay();
  expect(screen.getByTestId('relay-skip-note').textContent).toContain('Run ended early: no confirmed findings.');
  expect((section.textContent?.match(/no confirmed findings/g) ?? [])).toHaveLength(1);
});

it('selects a row and calls onSelect when it is clicked', () => {
  const onSelect = vi.fn();
  renderRelay('scout', onSelect);
  const scout = screen.getByTestId('relay-scout');
  expect(scout.getAttribute('aria-pressed')).toBe('true');
  fireEvent.click(scout);
  expect(onSelect).toHaveBeenCalledWith('scout');
});

it('shows the pipeline summary counts', () => {
  const summary = renderRelay().querySelector('[data-testid="relay-summary"]');
  expect([...summary!.querySelectorAll('.pipeline-stat strong')].map(value => value.textContent)).toEqual(['2', '4', '3', '2']);
});
