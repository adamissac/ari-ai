import { describe, expect, it } from 'vitest';
import { demoOnlyRedirects } from '@/lib/deployment';

describe('demo-only deployment', () => {
  it('redirects nothing in a normal build', () => {
    expect(demoOnlyRedirects(false)).toEqual([]);
  });

  it('sends the console routes to the access-code sign-in when there is no backend', () => {
    const redirects = demoOnlyRedirects(true);
    expect(redirects.map(r => r.source)).toEqual(['/projects', '/projects/:path*', '/connect', '/connect/:path*']);
    for (const r of redirects) {
      expect(r.destination).toBe('/access');
      expect(r.permanent).toBe(false);
    }
  });
});
