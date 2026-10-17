import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { renderToString } from 'react-dom/server';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { SiteNavigation } from '@/components/site-navigation';

let pathname = '/';
vi.mock('next/navigation', () => ({ usePathname: () => pathname }));
vi.mock('@/components/account-link', () => ({ AccountLink: () => <a href="#account">Sign in</a> }));
beforeEach(() => {
  pathname = '/';
  Object.defineProperty(window, 'scrollY', { configurable: true, writable: true, value: 0 });
});
afterEach(cleanup);
const scrollTo = (y: number) => act(() => { Object.defineProperty(window, 'scrollY', { configurable: true, value: y }); fireEvent.scroll(window); });

it('reserves an inert hidden group at the top, reveals at 100px and hides on return', () => {
  const { container } = render(<SiteNavigation />);
  const links = container.querySelector('#primary-links')!;
  expect(links.getAttribute('data-visible')).toBe('false');
  expect(links.hasAttribute('inert')).toBe(true);
  expect(screen.queryByRole('link', { name: 'Projects' })).toBeNull();
  expect(screen.getByRole('link', { name: 'Sign in' })).toBeTruthy();
  scrollTo(99);
  expect(links.getAttribute('data-visible')).toBe('false');
  scrollTo(100);
  expect(links.getAttribute('data-visible')).toBe('true');
  expect(links.hasAttribute('inert')).toBe(false);
  expect(screen.getByRole('link', { name: 'Pricing' })).toBeTruthy();
  scrollTo(130); // decreasing scroll position above the threshold still shows everything
  scrollTo(110);
  expect(links.getAttribute('data-visible')).toBe('true');
  scrollTo(0);
  expect(links.getAttribute('aria-hidden')).toBe('true');
  expect(links.hasAttribute('inert')).toBe(true);
});

it('keeps full navigation on other pages, including after returning home', () => {
  const { rerender, container } = render(<SiteNavigation />);
  fireEvent.click(screen.getByRole('button', { name: 'Menu' }));
  expect(container.querySelector('#primary-links')!.getAttribute('data-visible')).toBe('true');
  pathname = '/pricing'; rerender(<SiteNavigation />);
  expect(screen.getByRole('link', { name: 'Projects' })).toBeTruthy();
  expect(container.querySelector('#primary-links')!.hasAttribute('inert')).toBe(false);
  pathname = '/'; rerender(<SiteNavigation />);
  expect(container.querySelector('#primary-links')!.hasAttribute('inert')).toBe(true);
});

it('allows explicit mobile menu access and closes it on scroll reveal', () => {
  const { container } = render(<SiteNavigation />);
  const menu = screen.getByRole('button', { name: 'Menu' });
  fireEvent.click(menu);
  expect(menu.getAttribute('aria-expanded')).toBe('true');
  expect(container.querySelector('#primary-links')!.hasAttribute('inert')).toBe(false);
  fireEvent.click(menu);
  expect(container.querySelector('#primary-links')!.hasAttribute('inert')).toBe(true);
  fireEvent.click(menu);
  scrollTo(100);
  expect(menu.getAttribute('aria-expanded')).toBe('false');
  scrollTo(0);
  expect(container.querySelector('#primary-links')!.hasAttribute('inert')).toBe(true);
});

it('uses the restored scroll position on mount but renders the server top state safely', () => {
  scrollTo(200);
  expect(renderToString(<SiteNavigation />)).toContain('inert=""');
  const { container } = render(<SiteNavigation />);
  expect(container.querySelector('#primary-links')!.getAttribute('data-visible')).toBe('true');
});
