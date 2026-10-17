import { cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { HeaderContrast, isDarkSurface } from '@/components/header-contrast';

vi.mock('next/navigation', () => ({ usePathname: () => '/' }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); Reflect.deleteProperty(document, 'elementsFromPoint'); });

it('uses the nearest opaque surface, including light cards on a dark section', () => {
  const { container } = render(<section style={{ backgroundColor: '#1c1210' }}><div><span data-testid="dark" /></div><div style={{ backgroundColor: '#fff' }}><span data-testid="light" /></div></section>);
  expect(isDarkSurface(container.querySelector('[data-testid="dark"]'))).toBe(true);
  expect(isDarkSurface(container.querySelector('[data-testid="light"]'))).toBe(false);
  expect(isDarkSurface(null)).toBe(false);
});

it('ignores translucent decorations and keeps white text over the brand background', () => {
  const { container } = render(<section style={{ backgroundColor: '#c2452d' }}><span style={{ backgroundColor: 'rgba(255, 255, 255, 0.1)' }} /></section>);
  expect(isDarkSurface(container.querySelector('span'))).toBe(true);
});

it('ignores header hit targets, adapts on scroll and preserves the Pricing CTA', () => {
  let frame: FrameRequestCallback | undefined;
  vi.stubGlobal('requestAnimationFrame', vi.fn((callback: FrameRequestCallback) => { frame = callback; return 1; }));
  vi.stubGlobal('cancelAnimationFrame', vi.fn());
  const { container, unmount } = render(<><header className="site-header"><a href="#home">ARI</a><a className="hdr-cta" href="#pricing">Pricing</a></header><section style={{ backgroundColor: '#1c1210' }}>Dark section</section><HeaderContrast /></>);
  const logo = container.querySelector('a')!;
  const section = container.querySelector('section')!;
  Object.defineProperty(document, 'elementsFromPoint', { configurable: true, value: vi.fn(() => [logo, section]) });
  frame!(0);
  expect(logo.dataset.navTone).toBe('dark');
  expect(container.querySelector('.hdr-cta')!.getAttribute('data-nav-tone')).toBeNull();
  section.style.backgroundColor = '#fff';
  fireEvent.scroll(window);
  frame!(16);
  expect(logo.dataset.navTone).toBe('light');
  unmount();
  expect(cancelAnimationFrame).toHaveBeenCalled();
});
