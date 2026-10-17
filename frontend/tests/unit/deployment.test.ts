import { describe, expect, it } from 'vitest';
import { demoOnlyRedirects } from '@/lib/deployment';

describe('demo-only deployment', () => {
  it('redirects nothing in a normal build', () => {
    expect(demoOnlyRedirects(false)).toEqual([]);
  });

  it('sends the console routes to the simulated demo when there is no backend', () => {
    const redirects = demoOnlyRedirects(true);
    expect(redirects.map(r => r.source)).toEqual(['/projects', '/projects/:path*']);
    for (const r of redirects) {
      expect(r.destination).toBe('/demo');
      expect(r.permanent).toBe(false);
    }
  });
});
