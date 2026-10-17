import { cleanup, render } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';

vi.mock('next/navigation', () => ({ usePathname: () => '/' }));
import { SmoothScroll } from '@/components/smooth-scroll';

let frames: FrameRequestCallback[] = [];
let positions: number[] = [];
let reduced = false;

let clock = 0;
function flush(n = 400, frameMs = 1000 / 60) {
  for (let i = 0; i < n && frames.length; i++) {
    const run = frames; frames = [];
    clock += frameMs;
    run.forEach(f => f(clock));
  }
}

beforeEach(() => {
  frames = []; positions = []; reduced = false;
  vi.stubGlobal('requestAnimationFrame', (f: FrameRequestCallback) => { frames.push(f); return frames.length; });
  vi.stubGlobal('cancelAnimationFrame', () => { frames = []; });
  vi.stubGlobal('matchMedia', (q: string) => ({ matches: q.includes('reduced-motion') ? reduced : false, addEventListener() {}, removeEventListener() {} }));
  Object.defineProperty(document.documentElement, 'scrollHeight', { configurable: true, value: 5000 });
  Object.defineProperty(window, 'innerHeight', { configurable: true, value: 800 });
  Object.defineProperty(window, 'scrollY', { configurable: true, writable: true, value: 0 });
  window.scrollTo = ((_x: number, y: number) => { positions.push(y); (window as { scrollY: number }).scrollY = y; }) as typeof window.scrollTo;
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const wheel = (target: EventTarget, init: WheelEventInit) => {
  const e = new WheelEvent('wheel', { bubbles: true, cancelable: true, ...init });
  target.dispatchEvent(e);
  return e;
};

it('eases a wheel flick to its target instead of jumping', () => {
  render(<SmoothScroll />);
  const e = wheel(document.body, { deltaY: 600 });
  expect(e.defaultPrevented).toBe(true);
  flush();
  expect(positions.length).toBeGreaterThan(5);           // many small steps
  expect(positions[0]).toBeLessThan(600);                // first frame is not the full jump
  expect(positions.every((y, i) => i === 0 || y >= positions[i - 1]!)).toBe(true); // monotonic
  expect(positions.at(-1)).toBe(600);                    // lands exactly on target
});

it('clamps to the page and leaves pinch-zoom and horizontal gestures native', () => {
  render(<SmoothScroll />);
  wheel(document.body, { deltaY: 99999 });
  flush();
  expect(positions.at(-1)).toBe(4200); // scrollHeight - innerHeight
  expect(wheel(document.body, { deltaY: 100, ctrlKey: true }).defaultPrevented).toBe(false);
  expect(wheel(document.body, { deltaX: 300, deltaY: 10 }).defaultPrevented).toBe(false);
});

it('lets nested scroll areas scroll natively', () => {
  render(<SmoothScroll />);
  const box = document.createElement('div');
  box.style.overflowY = 'auto';
  Object.defineProperty(box, 'scrollHeight', { value: 1000 });
  Object.defineProperty(box, 'clientHeight', { value: 200 });
  document.body.appendChild(box);
  expect(wheel(box, { deltaY: 100 }).defaultPrevented).toBe(false);
  box.remove();
});

it('stays native for reduced-motion users', () => {
  reduced = true;
  render(<SmoothScroll />);
  expect(wheel(document.body, { deltaY: 600 }).defaultPrevented).toBe(false);
  expect(frames.length).toBe(0);
});

it('glides the same distance per second at 60 Hz and 120 Hz', () => {
  render(<SmoothScroll />);
  wheel(document.body, { deltaY: 600 });
  flush(30, 1000 / 60); // half a second at 60 Hz
  const at60 = positions.at(-1)!;
  cleanup(); positions = []; frames = []; (window as { scrollY: number }).scrollY = 0;
  render(<SmoothScroll />);
  wheel(document.body, { deltaY: 600 });
  flush(60, 1000 / 120); // half a second at 120 Hz
  expect(Math.abs(positions.at(-1)! - at60)).toBeLessThan(8);
});
