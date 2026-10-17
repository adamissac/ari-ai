import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { RecordedLiveRun } from '@/components/demo/recorded-live-run';
import { SiteFooter } from '@/components/site-footer';

vi.mock('next/navigation', () => ({ usePathname: () => '/demo/lumen-pay' }));
afterEach(cleanup);

it('labels the recorded live run as recorded, with no sample-data tag or footer on the account', () => {
  render(<><RecordedLiveRun /><SiteFooter /></>);
  expect(screen.queryByTestId('site-footer')).toBeNull();
  expect(screen.queryByTestId('demo-account-tag')).toBeNull();
  expect(screen.getByTestId('recorded-live-run').textContent).toContain('not simulated');
});

it('states the recorded run did not prove new tests failed before the patch', () => {
  render(<RecordedLiveRun />);
  const panel = screen.getByTestId('recorded-live-run');
  expect(panel.textContent).toContain('not run on the unpatched snapshot');
  expect(panel.textContent).toContain('does not establish red-to-green proof');
});
