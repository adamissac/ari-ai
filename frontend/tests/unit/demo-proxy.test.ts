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

  it('with the access cookie, legacy demo and sign-in routes open the Lumen Pay account instead', () => {
    vi.stubEnv('DEMO_ACCESS_CODE', 'test');
    const token = demoAccessToken()!;
    expect(proxy(req('/demo/lumen-pay', token)).headers.get('location')).toBe('https://ari.test/projects/prj_01M6FTWETXBNGJRSYY6JDZMTPS');
    for (const path of ['/projects', '/projects/p1']) expect(proxy(req(path, token)).headers.get('location')).toBeNull();
    for (const path of ['/connect', '/access']) expect(proxy(req(path, token)).headers.get('location')).toBe('https://ari.test/projects/prj_01M6FTWETXBNGJRSYY6JDZMTPS');
  });
});
