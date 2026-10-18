import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { along, buildTrail, colonySize, firstWave, NESTS, spawnGap, TRAILS } from '@/components/ant-colony';
import { HeroStage } from '@/components/hero';

beforeEach(() => { vi.stubGlobal('matchMedia', (q: string) => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('trails are closed loops', () => {
  for (const curve of TRAILS) {
    const t = buildTrail(curve, 1200, 800);
    const first = t.pts[0]!;
    const last = t.pts[t.pts.length - 1]!;
    expect(Math.hypot(first.x - last.x, first.y - last.y)).toBeLessThan(0.5);
  }
});

it('ants come out of nests spread around the hero: right, left, top and bottom', () => {
  const trails = TRAILS.map(c => buildTrail(c, 1200, 800));
  const nests = NESTS.map(n => along(trails[n.trail]!, n.at * trails[n.trail]!.length).p);
  expect(nests.length).toBeGreaterThanOrEqual(4);
  expect(Math.max(...nests.map(p => p.x))).toBeGreaterThan(1200 * 0.85);
  expect(Math.min(...nests.map(p => p.x))).toBeLessThan(1200 * 0.25);
  expect(Math.min(...nests.map(p => p.y))).toBeLessThan(800 * 0.3);
  expect(Math.max(...nests.map(p => p.y))).toBeGreaterThan(800 * 0.7);
  for (let i = 0; i < nests.length; i++) for (let j = i + 1; j < nests.length; j++) {
    expect(Math.hypot(nests[i]!.x - nests[j]!.x, nests[i]!.y - nests[j]!.y)).toBeGreaterThan(200);
  }
});

it('the colony starts with a first wave, more than one ant but well under the cap', () => {
  expect(firstWave(colonySize(375, 812))).toBe(5);
  expect(firstWave(colonySize(1440, 900))).toBe(10);
  expect(firstWave(34)).toBeLessThan(34);
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
