import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ProductTour } from '@/components/product-tour';

beforeEach(() => {
  vi.stubGlobal('matchMedia', vi.fn(() => ({
    matches: false,
    media: '(prefers-reduced-motion: reduce)',
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })));
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

it('shows four selectable steps with step-specific screenshots', () => {
  render(<ProductTour />);
  const tabs = screen.getAllByRole('tab');
  const expectedAlts = ['repository picker', 'code review tab', 'seven security agents', 'network map'] as const;
  expect(tabs).toHaveLength(4);
  expect(tabs[0]!.getAttribute('aria-selected')).toBe('true');
  fireEvent.click(tabs[1]!);
  expect(tabs[1]!.getAttribute('aria-selected')).toBe('true');
  expect(screen.getByRole('img').getAttribute('alt')).toMatch(/code review tab/);

  for (const [index, tab] of tabs.entries()) {
    fireEvent.click(tab);
    expect(screen.getByRole('img').getAttribute('alt')).toMatch(new RegExp(expectedAlts[index]!));
  }
});

it('does not auto-advance when reduced motion is preferred', () => {
  vi.useFakeTimers();
  class VisibleObserver {
    constructor(private callback: IntersectionObserverCallback) {}
    observe() { this.callback([{ isIntersecting: true } as IntersectionObserverEntry], this as unknown as IntersectionObserver); }
    disconnect() {}
    unobserve() {}
    takeRecords() { return []; }
  }
  vi.stubGlobal('IntersectionObserver', VisibleObserver);
  vi.stubGlobal('matchMedia', vi.fn(() => ({
    matches: true,
    media: '(prefers-reduced-motion: reduce)',
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })));
  render(<ProductTour />);
  act(() => { vi.advanceTimersByTime(20); });
  expect(screen.getAllByRole('tab')[0]!.getAttribute('aria-selected')).toBe('true');
  act(() => { vi.advanceTimersByTime(8000); });
  expect(screen.getAllByRole('tab')[0]!.getAttribute('aria-selected')).toBe('true');
});
