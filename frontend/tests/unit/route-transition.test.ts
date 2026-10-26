import { act, render } from '@testing-library/react';
import { createElement } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { RouteTransition, playsTransition, sectionOf } from '@/components/route-transition';

vi.mock('next/navigation', () => ({ usePathname: () => '/pricing' }));

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

it('covers a cross-section navigation with the ring loader around the mark', () => {
  Object.defineProperty(window, 'matchMedia', { configurable: true, value: () => ({ matches: false }) });
  window.history.replaceState(null, '', '/pricing');
  const { container } = render(createElement('div', null, createElement(RouteTransition), createElement('a', { href: '/lab' }, 'Defense Lab')));
  const link = container.querySelector('a') as HTMLAnchorElement;
  link.addEventListener('click', e => e.preventDefault());
  act(() => { link.click(); });
  const veil = container.querySelector('.route-veil');
  expect(veil?.querySelector('svg.intro-ring .intro-ring-fill')).not.toBeNull();
  expect(veil?.querySelector('.intro-pct')?.textContent).toMatch(/^\d+%$/);
  expect(veil?.querySelector('.route-veil-line')).toBeNull();
});
