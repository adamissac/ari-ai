import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { Async } from '@/components/ui';

afterEach(cleanup);

it('says when the data on screen is a stale copy and offers a retry', () => {
  const reload = vi.fn();
  render(<Async resource={{ status: 'ready', data: 'old', error: undefined, reload, refreshError: new Error('offline') }} label="approvals">{data => <p>{data}</p>}</Async>);
  expect(screen.getByText('old')).toBeTruthy();
  expect(screen.getByTestId('stale-notice').textContent).toContain('Could not refresh approvals');
  fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
  expect(reload).toHaveBeenCalled();
});

it('shows no notice for fresh data', () => {
  render(<Async resource={{ status: 'ready', data: 'new', error: undefined, reload: vi.fn() }} label="approvals">{data => <p>{data}</p>}</Async>);
  expect(screen.queryByTestId('stale-notice')).toBeNull();
});
