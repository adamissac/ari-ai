import { render, screen } from '@testing-library/react';
import { expect, it } from 'vitest';
import { SetupSteps } from '@/components/onboarding/stepper';

it('renders seven ordered steps with done/current states and aria-current', () => {
  render(<SetupSteps current={5} org="acme" doneSteps={[1, 2, 3, 4]} onStepChange={() => {}} />);
  const items = screen.getAllByRole('listitem');
  expect(items.map(item => item.textContent?.trim())).toEqual([
    '01Connect GitHub',
    '02Choose repository',
    '03Readiness',
    '04Review behavior',
    '05Testing scope',
    '06Fix delivery',
    '07Review & start',
  ]);
  expect(items.map(item => item.getAttribute('data-step-state'))).toEqual([
    'done', 'done', 'done', 'done', 'current', 'upcoming', 'upcoming',
  ]);
  expect(screen.getByRole('button', { name: /Testing scope/ }).getAttribute('aria-current')).toBe('step');
  expect(screen.getByText('Step 5 of 7 · Testing scope')).toBeTruthy();
});
