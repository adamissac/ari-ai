import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import Link from 'next/link';
import { afterEach, expect, it, vi } from 'vitest';
import { CoachMark } from '@/components/onboarding/coach-mark';

afterEach(cleanup);

it('highlights the answer area while Got it hides only the setup tip', () => {
  render(
    <>
      <div data-coach="setup-interactive">
        <button type="button">Continue</button>
      </div>
      <CoachMark mode="setup" target="setup-interactive" current={1} total={8}>Check the repository and branch.</CoachMark>
    </>,
  );
  const dialog = screen.getByRole('dialog', { name: 'Setup tip' });
  expect(document.activeElement).toBe(dialog);
  expect(screen.getByTestId('coach-spotlight')).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Continue' })).toBeTruthy();
  expect(screen.queryByText(/Question \d of \d/)).toBeNull();
  fireEvent.keyDown(window, { key: 'Escape' });
  fireEvent.click(screen.getByRole('button', { name: 'Got it' }));
  expect(screen.queryByRole('dialog')).toBeNull();
  expect(screen.getByTestId('coach-spotlight')).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Continue' })).toBeTruthy();
});

it('shows a numbered tab-tour tip with only Skip tour and Next', () => {
  const next = vi.fn();
  const skip = vi.fn();
  render(
    <>
      <Link data-coach="analytics" href="/">Analytics</Link>
      <CoachMark mode="tour" target="analytics" current={1} total={6} onNext={next} onSkip={skip}>Analytics summarizes saved checks.</CoachMark>
    </>,
  );
  const dialog = screen.getByRole('dialog', { name: 'Tip 1 of 6' });
  expect(document.activeElement).toBe(dialog);
  fireEvent.click(screen.getByRole('button', { name: 'Next' }));
  fireEvent.click(screen.getByRole('button', { name: 'Skip tour' }));
  expect(next).toHaveBeenCalledOnce();
  expect(skip).toHaveBeenCalledOnce();
  expect(screen.queryByRole('button', { name: 'Back' })).toBeNull();
});
