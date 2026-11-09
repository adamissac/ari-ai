import { NextRequest } from 'next/server';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { DEMO_COOKIE, demoAccessToken } from '@/lib/demo/access';
import { proxy } from '@/proxy';

const req = (path: string, cookie?: string) =>
  new NextRequest(`https://ari.test${path}`, cookie ? { headers: { cookie: `${DEMO_COOKIE}=${cookie}` } } : undefined);

afterEach(() => vi.unstubAllEnvs());

describe('demo access proxy', () => {
  it('without the access cookie, /demo goes to the code page and the console is untouched', () => {
    vi.stubEnv('DEMO_ACCESS_CODE', 'test');
    expect(proxy(req('/demo/lumen-pay')).headers.get('location')).toBe('https://ari.test/access');
    expect(proxy(req('/projects')).headers.get('location')).toBeNull();
  });

  it('with the access cookie, the console opens in place and legacy demo routes open the organization picker', () => {
    vi.stubEnv('DEMO_ACCESS_CODE', 'test');
    const token = demoAccessToken()!;
    expect(proxy(req('/demo/lumen-pay', token)).headers.get('location')).toBe('https://ari.test/connect');
    expect(proxy(req('/access', token)).headers.get('location')).toBe('https://ari.test/connect');
    for (const path of ['/projects', '/projects/p1', '/connect', '/connect/lumen-pay', '/access/github']) expect(proxy(req(path, token)).headers.get('location')).toBeNull();
  });

  it('the simulated GitHub step needs the access cookie', () => {
    vi.stubEnv('DEMO_ACCESS_CODE', 'test');
    expect(proxy(req('/access/github')).headers.get('location')).toBe('https://ari.test/access');
  });
});
