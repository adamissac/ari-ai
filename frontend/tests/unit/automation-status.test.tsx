import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { AutomationStatus } from '@/components/automation-status';

const mocks = vi.hoisted(() => ({ useResource: vi.fn() }));
vi.mock('@/lib/use-resource', () => ({ useResource: mocks.useResource }));
afterEach(cleanup);

it('shows the derived state and every reason, not the project switch alone', () => {
  mocks.useResource.mockReturnValue({ status: 'ready', reload: vi.fn(), data: {
    repo_id: 'rep_1', state: 'off', resets_at: null,
    reasons: [{ code: 'repository_off', message: 'Automatic reviews are off for this repository.' }],
  } });
  render(<AutomationStatus repoId="rep_1" />);
  expect(screen.getByTestId('automation-status').getAttribute('data-state')).toBe('off');
  expect(screen.getByText(/Automatic reviews: Off/)).toBeTruthy();
  expect(screen.getByText('Automatic reviews are off for this repository.')).toBeTruthy();
});

it('says when it could not check instead of guessing', () => {
  mocks.useResource.mockReturnValue({ status: 'error', error: new Error('x'), reload: vi.fn() });
  render(<AutomationStatus repoId="rep_1" />);
  expect(screen.getByText(/unknown \(could not check\)/)).toBeTruthy();
});
