import { describe, expect, it } from 'vitest';
import { playsTransition, sectionOf } from '@/components/route-transition';

describe('page transition', () => {
  it('groups paths into parts of the site', () => {
    expect(sectionOf('/')).toBe('home');
    expect(sectionOf('/projects/prj_1/findings')).toBe('console');
    expect(sectionOf('/connect/acme')).toBe('console');
    expect(sectionOf('/lab')).toBe('lab');
    expect(sectionOf('/demo/lumen-pay/payments-api')).toBe('demo');
  });

  it('plays only between different parts, never into the landing or API routes', () => {
    expect(playsTransition('/projects', '/lab')).toBe(true);
    expect(playsTransition('/lab', '/pricing')).toBe(true);
    expect(playsTransition('/', '/projects')).toBe(true);
    expect(playsTransition('/projects/prj_1', '/projects/prj_1/findings')).toBe(false);
    expect(playsTransition('/projects', '/connect')).toBe(false);
    expect(playsTransition('/demo/lumen-pay', '/demo/lumen-pay/payments-api')).toBe(false);
    expect(playsTransition('/lab', '/')).toBe(false);
    expect(playsTransition('/projects', '/api/v1/auth/github/login')).toBe(false);
  });
});
