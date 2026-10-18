import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { along, buildTrail, colonySize, spawnGap, TRAILS } from '@/components/ant-colony';
import { HeroStage } from '@/components/hero';

beforeEach(() => { vi.stubGlobal('matchMedia', (q: string) => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('trails are closed loops that start at the nest on the right', () => {
  for (const curve of TRAILS) {
    const t = buildTrail(curve, 1200, 800);
    const first = t.pts[0]!;
    const last = t.pts[t.pts.length - 1]!;
    expect(Math.hypot(first.x - last.x, first.y - last.y)).toBeLessThan(0.5);
    expect(first.x).toBeGreaterThan(1200 * 0.85);
  }
});

it('ants walk at constant speed along the trail, and distance wraps around', () => {
  const t = buildTrail(TRAILS[0]!, 1200, 800);
  const steps = Array.from({ length: 40 }, (_, i) => along(t, (i * t.length) / 40).p);
  const gaps = steps.slice(1).map((p, i) => Math.hypot(p.x - steps[i]!.x, p.y - steps[i]!.y));
  const mean = gaps.reduce((a, b) => a + b, 0) / gaps.length;
  for (const g of gaps) expect(Math.abs(g - mean) / mean).toBeLessThan(0.1);
  const a = along(t, 10).p;
  const b = along(t, 10 + t.length).p;
  expect(Math.hypot(a.x - b.x, a.y - b.y)).toBeLessThan(1e-6);
});

it('the colony grows to a modest size, slowly at first then faster', () => {
  expect(colonySize(375, 812)).toBe(10);
  expect(colonySize(1440, 900)).toBe(34);
  expect(colonySize(5000, 3000)).toBe(34);
  const gaps = [0, 5, 10, 20, 30].map(n => spawnGap(n, 34));
  for (let i = 1; i < gaps.length; i++) expect(gaps[i]!).toBeLessThanOrEqual(gaps[i - 1]!);
  expect(Math.min(...gaps)).toBeGreaterThan(0.4);
});

it('only the landing hero draws the colony, as a decorative canvas', () => {
  const { rerender } = render(<HeroStage labelledBy="t" colony><h1 id="t">Hi</h1></HeroStage>);
  expect(screen.getByTestId('ant-colony').getAttribute('aria-hidden')).toBe('true');
  rerender(<HeroStage labelledBy="t"><h1 id="t">Hi</h1></HeroStage>);
  expect(screen.queryByTestId('ant-colony')).toBeNull();
});
