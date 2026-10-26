import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { CoachMark } from '@/components/onboarding/coach-mark';

afterEach(cleanup);

it('focuses its bubble, supports keyboard activation, and cannot be escaped', () => {
  const next = vi.fn();
  const back = vi.fn();
  const skip = vi.fn();
  render(
    <>
      <button data-coach="analytics">Analytics target</button>
      <CoachMark target="analytics" current={1} total={6} onNext={next} onBack={back} onSkip={skip}>Analytics guidance.</CoachMark>
    </>,
  );
  const dialog = screen.getByRole('dialog', { name: 'Setup guidance, question 1 of 6' });
  expect(document.activeElement).toBe(dialog);
  fireEvent.keyDown(window, { key: 'Escape' });
  expect(skip).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Next' }));
  expect(next).toHaveBeenCalledOnce();
  fireEvent.click(screen.getByRole('button', { name: 'Back' }));
  expect(back).toHaveBeenCalledOnce();
  expect(screen.getByRole('button', { name: 'Skip tour' })).toBeTruthy();
});
