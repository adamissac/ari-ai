import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SignalField } from '@/components/marketing/signal-field';

const stages = 'commit trace flag check patch verify';

class IntersectionObserverStub {
  static instances: IntersectionObserverStub[] = [];
  readonly observe = vi.fn();
  readonly disconnect = vi.fn();
  readonly unobserve = vi.fn();

  constructor(private callback: IntersectionObserverCallback) {
    IntersectionObserverStub.instances.push(this);
  }

  trigger(isIntersecting: boolean) {
    this.callback([{ isIntersecting } as IntersectionObserverEntry], this as unknown as IntersectionObserver);
  }
}

beforeEach(() => { IntersectionObserverStub.instances = []; });
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('SignalField', () => {
  it('shows the complete sequence immediately for reduced motion', () => {
    const matchMedia = vi.fn((query: string) => ({
      matches: query.includes('prefers-reduced-motion'),
      media: query,
      addEventListener() {},
      removeEventListener() {},
    }));
    vi.stubGlobal('matchMedia', matchMedia);
    vi.stubGlobal('IntersectionObserver', IntersectionObserverStub);

    render(<SignalField />);

    expect(matchMedia).toHaveBeenCalledWith('(prefers-reduced-motion: reduce)');
    expect(screen.getByTestId('signal-field').getAttribute('data-s')).toBe(stages);
    expect(IntersectionObserverStub.instances).toHaveLength(0);
  });

  it('advances from commit to trace and pauses while it is off-screen', () => {
    vi.useFakeTimers();
    vi.stubGlobal('matchMedia', (query: string) => ({
      matches: false,
      media: query,
      addEventListener() {},
      removeEventListener() {},
    }));
    vi.stubGlobal('IntersectionObserver', IntersectionObserverStub);

    render(<SignalField />);
    const field = screen.getByTestId('signal-field');
    const observer = IntersectionObserverStub.instances[0]!;

    act(() => observer.trigger(true));
    act(() => { vi.advanceTimersByTime(400); });
    expect(field.getAttribute('data-s')).toBe('commit');

    act(() => observer.trigger(false));
    act(() => { vi.advanceTimersByTime(5000); });
    expect(field.getAttribute('data-s')).toBe('commit');

    act(() => observer.trigger(true));
    act(() => { vi.advanceTimersByTime(400); });
    act(() => { vi.advanceTimersByTime(1600); });
    expect(field.getAttribute('data-s')).toBe('commit trace');
  });
});
