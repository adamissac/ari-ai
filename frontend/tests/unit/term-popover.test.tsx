import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { Term, popoverAlign } from '@/components/term';

afterEach(cleanup);

it('aligns left in the left half and right in the right half', () => {
  expect(popoverAlign(20, 40, 375)).toBe('left');
  expect(popoverAlign(300, 50, 375)).toBe('right');
});

it('caps width and right-aligns when the trigger is near the right edge', () => {
  Object.defineProperty(window, 'innerWidth', { value: 375, configurable: true });
  render(<Term t="finding" />);
  const btn = screen.getByTestId('term-finding');
  btn.getBoundingClientRect = () => ({ left: 300, width: 60, right: 360, top: 0, bottom: 10, height: 10, x: 300, y: 0, toJSON() {} });
  fireEvent.click(btn);
  const note = screen.getByRole('note');
  expect(note.className).toContain('max-w-[calc(100vw-2rem)]');
  expect(note.className).toContain('right-0');
  expect(btn.getAttribute('aria-expanded')).toBe('true');
  fireEvent.keyDown(document, { key: 'Escape' });
  expect(screen.queryByRole('note')).toBeNull();
});
