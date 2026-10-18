import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { AttackDrill } from '@/components/attack-drill';

const startAttackDrill = vi.hoisted(() => vi.fn());
vi.mock('@/lib/api', () => ({ api: () => ({ startAttackDrill }) }));
afterEach(() => { cleanup(); startAttackDrill.mockReset(); });

it('labels real routes, synthetic counters and optional model use accurately', () => {
  render(<AttackDrill projectId="prj_test" onEvents={vi.fn()} />);
  const badge = screen.getByTestId('attack-drill-provenance');
  expect(badge.textContent).toBe('Synthetic drill · no service traffic');
  expect(badge.title).toContain('real project routes');
  expect(badge.title).toContain('synthetic counters');
  expect(badge.title).toContain('Claude or use a scripted fallback');
  expect(badge.title).toContain('no response action is executed');
  expect(badge.title).not.toMatch(/No repository is accessed|no model is called|illustrative accounts/i);
  expect(screen.queryByTestId('demo-marker')).toBeNull();
});

it('uses provenance-neutral running copy before the planner is known', async () => {
  startAttackDrill.mockResolvedValue({ job_id: 'job_ui_fixture' });
  render(<AttackDrill projectId="prj_test" onEvents={vi.fn()} />);
  fireEvent.click(screen.getByRole('button', { name: 'Run an attack drill' }));
  expect(await screen.findByRole('button', { name: 'Running drill…' })).toHaveProperty('disabled', true);
  expect(startAttackDrill).toHaveBeenCalledWith('prj_test');
  expect(screen.queryByText('Claude is attacking…')).toBeNull();
});
