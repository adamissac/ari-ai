import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const app = path.resolve(import.meta.dirname, '../../app');
const tokens = readFileSync(path.resolve(app, 'tokens.css'), 'utf8');
const globals = readFileSync(path.resolve(app, 'globals.css'), 'utf8');
const interfaceCss = readFileSync(path.resolve(app, 'interface.css'), 'utf8');

const token = (name: string) => {
  const match = tokens.match(new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})`));
  if (!match) throw new Error(`token ${name} missing`);
  return match[1]!;
};
const luminance = (hex: string) => {
  const channels = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255);
  const [r, g, b] = channels.map(v => v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
  return 0.2126 * r! + 0.7152 * g! + 0.0722 * b!;
};
const contrast = (a: string, b: string) => {
  const [x, y] = [luminance(a), luminance(b)];
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
};

describe('Industrial Graphite design tokens', () => {
  it('uses the specified graphite and signal palette', () => {
    expect(token('surface-0')).toBe('#0B0B0D');
    expect(token('surface-1')).toBe('#141416');
    expect(token('surface-2')).toBe('#1B1B1E');
    expect(token('signal')).toBe('#E5582F');
    expect(token('signal-deep')).toBe('#B8411F');
  });

  it('keeps all ink levels readable on the primary surfaces', () => {
    const surfaces = [token('surface-0'), token('surface-1')];
    for (const ink of ['ink-1', 'ink-2', 'ink-3']) {
      for (const surface of surfaces) expect(contrast(token(ink), surface)).toBeGreaterThanOrEqual(4.5);
    }
    expect(contrast(token('ink-4'), token('surface-0'))).toBeGreaterThanOrEqual(4.5);
  });

  it('keeps the signal distinguishable from the graphite surfaces', () => {
    for (const surface of [token('surface-0'), token('surface-1')]) {
      expect(contrast(token('signal'), surface)).toBeGreaterThanOrEqual(3);
    }
  });

  it('uses the signal focus ring and disables motion when requested', () => {
    expect(globals).toMatch(/:focus-visible\s*\{\s*outline:\s*2px solid var\(--signal\);\s*outline-offset:\s*2px/);
    expect(tokens).toMatch(/prefers-reduced-motion:\s*reduce[\s\S]*?transition-duration:\s*0\.01ms/);
  });

  it('does not scope the old night skin with :has() or render ambient layers', () => {
    expect(globals).not.toContain(':root:not(:has(.hero-full))');
    expect(interfaceCss).not.toContain(':root:not(:has(.hero-full))');
    expect(globals).not.toContain('.ambient-orb {');
  });
});
