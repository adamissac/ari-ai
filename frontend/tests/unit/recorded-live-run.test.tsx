import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { RecordedLiveRun } from '@/components/demo/recorded-live-run';
import { RECORDED_LIVE_RUN } from '@/lib/demo/recorded-live-run';

afterEach(cleanup);

describe('recorded live run panel', () => {
  it('labels the panel as a replay of a recorded run, not a live or simulated one', () => {
    render(<RecordedLiveRun />);
    const panel = screen.getByTestId('recorded-live-run');
    expect(panel.textContent).toContain(`Replay of recorded run ${RECORDED_LIVE_RUN.assessmentId}`);
    expect(panel.textContent).toContain('not a run happening now');
    expect(panel.textContent).toContain('not simulated');
  });

  it('shows all seven agents and the recorded cost from the saved report', () => {
    render(<RecordedLiveRun />);
    for (const agent of ['scout', 'probe', 'trace', 'diagnose', 'patch', 'verify', 'fortify']) {
      expect(screen.getByTestId(`recorded-agent-${agent}`).textContent).toContain('succeeded');
    }
    expect(screen.getByTestId('recorded-live-run').textContent).toContain('$1.39');
    expect(screen.getByTestId('recorded-states').textContent?.endsWith('completed')).toBe(true);
  });

  it('keeps the recorded run separate from the illustrative demo data', () => {
    const total = RECORDED_LIVE_RUN.agents.reduce((sum, a) => sum + a.usd, 0);
    expect(Math.abs(total - RECORDED_LIVE_RUN.usd)).toBeLessThan(0.01);
    expect(JSON.stringify(RECORDED_LIVE_RUN)).not.toMatch(/sk-ant-|fixture-token|Bearer /);
  });
});
