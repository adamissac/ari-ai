import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import PricingPage from '@/app/pricing/page';

afterEach(cleanup);

it('shows both plans, the FAQ and the preview-pricing note', () => {
  render(<PricingPage />);
  expect(screen.getByRole('heading', { level: 1, name: 'Ari AI pricing' })).toBeTruthy();
  expect(screen.getByRole('heading', { name: 'Team' })).toBeTruthy();
  expect(screen.getByRole('heading', { name: 'Enterprise' })).toBeTruthy();
  expect(screen.getByText('$40')).toBeTruthy();
  expect(screen.getByText('Custom pricing')).toBeTruthy();
  expect(screen.getByText('Recommended')).toBeTruthy();
  expect(screen.getByText('Does Ari AI ever change our code on its own?')).toBeTruthy();
  expect(screen.getByTestId('pricing-preview').textContent).toContain('nothing can be purchased');
  expect(screen.getByTestId('pricing-proposal').textContent).toContain('proposals');
  expect(screen.queryByText(/free trial/i)).toBeNull();
  expect(screen.queryByText(/SSO/)).toBeNull();
});
