import { cleanup, render } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { HeroStage } from '@/components/hero';

let frames: FrameRequestCallback[] = [];
let reduced = false;

function flush(n = 400) {
  for (let i = 0; i < n && frames.length; i++) {
    const run = frames;
    frames = [];
    run.forEach(f => f(performance.now()));
  }
}

beforeEach(() => {
  frames = [];
  reduced = false;
  vi.stubGlobal('requestAnimationFrame', (f: FrameRequestCallback) => {
    frames.push(f);
    return frames.length;
  });
  vi.stubGlobal('cancelAnimationFrame', () => {
    frames = [];
  });
  vi.stubGlobal('matchMedia', (q: string) => ({
    matches: q.includes('reduced-motion') ? reduced : false,
    addEventListener() {},
    removeEventListener() {},
  }));
  Object.defineProperty(window, 'scrollY', { configurable: true, writable: true, value: 0 });
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
    height: 1000,
    width: 1000,
    top: 0,
    left: 0,
    right: 1000,
    bottom: 1000,
    x: 0,
    y: 0,
    toJSON: () => ({}),
  } as DOMRect);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

it('eases the hero scroll progress toward the page instead of jumping', () => {
  const { container } = render(
    <HeroStage labelledBy="hero-title">
      <h1 id="hero-title">Hero</h1>
    </HeroStage>,
  );
  const hero = container.querySelector('section');
  expect(hero).not.toBeNull();

  flush();
  (window as { scrollY: number }).scrollY = 500;
  window.dispatchEvent(new Event('scroll'));
  flush(1);

  const early = Number(hero!.style.getPropertyValue('--scroll'));
  expect(early).toBeGreaterThan(0);
  expect(early).toBeLessThan(0.25);

  flush();
  expect(Number(hero!.style.getPropertyValue('--scroll'))).toBe(0.5);
});

it('updates the header state immediately while the hero motion settles', () => {
  render(
    <HeroStage labelledBy="hero-title">
      <h1 id="hero-title">Hero</h1>
    </HeroStage>,
  );

  (window as { scrollY: number }).scrollY = 500;
  window.dispatchEvent(new Event('scroll'));
  flush(1);

  expect(document.documentElement.dataset.heroScrolled).toBe('');
});

it('keeps the hero static for reduced-motion users', () => {
  reduced = true;
  const { container } = render(
    <HeroStage labelledBy="hero-title">
      <h1 id="hero-title">Hero</h1>
    </HeroStage>,
  );
  const hero = container.querySelector('section');

  (window as { scrollY: number }).scrollY = 500;
  window.dispatchEvent(new Event('scroll'));
  flush();

  expect(hero!.style.getPropertyValue('--scroll')).toBe('');
});
