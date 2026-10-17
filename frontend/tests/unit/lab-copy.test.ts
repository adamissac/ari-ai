import { describe, expect, it } from 'vitest';
import { countWord, defenderCountPhrase, machineCountPhrase } from '@/components/lab-copy';

const scenario = (n: number) => ({ nodes: Array.from({ length: n }, () => ({})) });

describe('lab copy', () => {
  it('words small counts and digits large ones', () => {
    expect(countWord(5)).toBe('five');
    expect(countWord(12)).toBe('12');
  });
  it('derives the machine count from scenarios', () => {
    expect(machineCountPhrase([scenario(5), scenario(5)])).toBe('five machines');
    expect(machineCountPhrase([scenario(4), scenario(6)])).toBe('four to six machines');
    expect(machineCountPhrase([scenario(1)])).toBe('one machine');
    expect(machineCountPhrase([])).toBe('machines');
  });
  it('derives the defender count', () => {
    expect(defenderCountPhrase(4, true)).toBe('Four defenders');
    expect(defenderCountPhrase(3)).toBe('three defenders');
    expect(defenderCountPhrase(1)).toBe('one defender');
  });
});
