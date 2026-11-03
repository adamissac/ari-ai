import { cleanup, render } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { AnchorScroll } from '@/components/anchor-scroll';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function setReducedMotion(matches: boolean) {
  vi.stubGlobal('matchMedia', () => ({ matches }) as MediaQueryList);
}

function click(element: Element, init: MouseEventInit = {}) {
  const event = new MouseEvent('click', { bubbles: true, cancelable: true, button: 0, ...init });
  element.dispatchEvent(event);
  return event;
}

it('leaves wheel events to native scrolling', () => {
  render(<AnchorScroll />);
  const event = new WheelEvent('wheel', { bubbles: true, cancelable: true, deltaY: 100 });
  document.dispatchEvent(event);
  expect(event.defaultPrevented).toBe(false);
});

it('smoothly scrolls to an existing same-page hash and records it', () => {
  setReducedMotion(false);
  const { container } = render(
    <>
      <AnchorScroll />
      <a href="#section">Section</a>
      <div id="section" />
    </>,
  );
  const element = container.querySelector<HTMLElement>('#section')!;
  const scrollIntoView = vi.fn();
  element.scrollIntoView = scrollIntoView;
  const pushState = vi.spyOn(window.history, 'pushState');

  const event = click(container.querySelector('a')!);

  expect(event.defaultPrevented).toBe(true);
  expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'start' });
  expect(pushState).toHaveBeenCalledWith(null, '', '#section');
});

it('does not intercept anchor clicks when reduced motion is requested', () => {
  setReducedMotion(true);
  const { container } = render(
    <>
      <AnchorScroll />
      <a href="#section">Section</a>
      <div id="section" />
    </>,
  );

  expect(click(container.querySelector('a')!).defaultPrevented).toBe(false);
});

it('does not intercept links to a different pathname', () => {
  setReducedMotion(false);
  const { container } = render(
    <>
      <AnchorScroll />
      <a href="/another-page#section">Section</a>
      <div id="section" />
    </>,
  );

  expect(click(container.querySelector('a')!).defaultPrevented).toBe(false);
});
