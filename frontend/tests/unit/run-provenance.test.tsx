import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

const state = vi.hoisted(() => ({ resource: { status: 'loading' } as Record<string, unknown> }));
vi.mock('@/lib/use-resource', () => ({ useResource: () => state.resource }));

import { RunProvenance } from '@/components/run-provenance';
import { hasNonLiveModelTurns } from '@/lib/status';

afterEach(() => { cleanup(); state.resource = { status: 'loading' }; });

const ready = (...modes: string[]) => {
  state.resource = { status: 'ready', data: { agent_runs: modes.map(provider_mode => ({ provider_mode })) }, reload: vi.fn() };
};

describe('live vs scripted provenance', () => {
  it('deterministic steps do not make a live run "not live"', () => {
    expect(hasNonLiveModelTurns(['live', 'none'])).toBe(false);
    expect(hasNonLiveModelTurns(['none'])).toBe(false);
    expect(hasNonLiveModelTurns(['live', 'fake'])).toBe(true);
    expect(hasNonLiveModelTurns(['replay'])).toBe(true);
    expect(hasNonLiveModelTurns(['something-new'])).toBe(true);
  });

  it('a finding from a live run shows no notice', () => {
    ready('live', 'none', 'live');
    render(<RunProvenance assessmentId="asm_1" />);
    expect(screen.queryByTestId('run-provenance')).toBeNull();
  });

  it('a finding from a scripted run says so on the finding page', () => {
    ready('fake', 'fake', 'none');
    render(<RunProvenance assessmentId="asm_1" />);
    const note = screen.getByTestId('run-provenance').textContent ?? '';
    expect(note).toMatch(/Not from a live-provider run/);
    expect(note).toMatch(/2 scripted/);
  });

  it('an unknown provenance is not presented as live', () => {
    state.resource = { status: 'error', error: new Error('x'), reload: vi.fn() };
    render(<RunProvenance assessmentId="asm_1" />);
    expect(screen.getByTestId('run-provenance').textContent).toMatch(/not known whether its model turns were live/);
  });
});
