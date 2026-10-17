import { afterEach, describe, expect, it } from 'vitest';
import { codeMatches, cookieGrantsAccess, demoAccessToken, DEMO_HOME, safeNext } from '@/lib/demo/access';

const ORIGINAL = process.env.DEMO_ACCESS_CODE;
afterEach(() => {
  if (ORIGINAL === undefined) delete process.env.DEMO_ACCESS_CODE;
  else process.env.DEMO_ACCESS_CODE = ORIGINAL;
});

describe('demo access code', () => {
  it('is closed when no code is configured', () => {
    delete process.env.DEMO_ACCESS_CODE;
    expect(demoAccessToken()).toBeNull();
    expect(codeMatches('')).toBe(false);
    expect(codeMatches('anything')).toBe(false);
    expect(cookieGrantsAccess('')).toBe(false);
  });

  it('accepts only the configured code and a cookie derived from it', () => {
    process.env.DEMO_ACCESS_CODE = 'correct horse';
    expect(codeMatches('correct horse')).toBe(true);
    expect(codeMatches(' correct horse ')).toBe(true);
    expect(codeMatches('correct')).toBe(false);
    expect(codeMatches(42)).toBe(false);
    const token = demoAccessToken();
    expect(token).toMatch(/^[0-9a-f]{64}$/);
    expect(token).not.toContain('correct');
    expect(cookieGrantsAccess(token ?? undefined)).toBe(true);
    expect(cookieGrantsAccess('1')).toBe(false);
    expect(cookieGrantsAccess(undefined)).toBe(false);
  });

  it('rotating the code invalidates existing cookies', () => {
    process.env.DEMO_ACCESS_CODE = 'first';
    const old = demoAccessToken() ?? undefined;
    process.env.DEMO_ACCESS_CODE = 'second';
    expect(cookieGrantsAccess(old)).toBe(false);
  });

  it('only redirects to demo paths after sign-in', () => {
    expect(safeNext('/demo/lumen-pay/payments-api')).toBe('/demo/lumen-pay/payments-api');
    expect(safeNext('/demo')).toBe('/demo');
    for (const bad of ['https://evil.example', '//evil.example', '/projects', '/demo?x=1', '/demox', null, undefined]) {
      expect(safeNext(bad)).toBe(DEMO_HOME);
    }
  });
});
