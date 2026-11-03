import { expect, it } from 'vitest';
import { chapterStep } from '@/components/story';

const stepRanges = (count: number, samples = 9000) => {
  const ranges = Array.from({ length: count }, () => 0);
  for (let i = 0; i <= samples; i++) ranges[chapterStep(i / samples, count)]! += 1 / samples;
  return ranges;
};

it('opens every step in order from the start to the end of the track', () => {
  expect(chapterStep(0, 4)).toBe(0);
  expect(chapterStep(1, 4)).toBe(3);
  expect(chapterStep(-0.2, 4)).toBe(0);
  expect(chapterStep(1.2, 4)).toBe(3);
  let previous = 0;
  for (let i = 0; i <= 1000; i++) {
    const step = chapterStep(i / 1000, 4);
    expect(step - previous === 0 || step - previous === 1).toBe(true);
    previous = step;
  }
});

it('gives the last step more scroll than the others so it is not skipped', () => {
  const [first, second, third, last] = stepRanges(4);
  expect(second).toBeCloseTo(first!, 2);
  expect(third).toBeCloseTo(first!, 2);
  expect(last).toBeCloseTo(first! * 1.5, 2);
});
