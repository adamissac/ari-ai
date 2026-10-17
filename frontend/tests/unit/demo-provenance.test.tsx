import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { DemoAccountTag } from '@/components/demo/ui';
import { RecordedLiveRun } from '@/components/demo/recorded-live-run';
import { SiteFooter } from '@/components/site-footer';

vi.mock('next/navigation', () => ({ usePathname: () => '/demo/lumen-pay' }));
afterEach(cleanup);

it('carves recorded evidence out of sample-account labels on the same screen', () => {
  render(<><DemoAccountTag /><RecordedLiveRun /><SiteFooter /></>);
  const footer = screen.getByTestId('site-footer');
  const tag = screen.getByTestId('demo-account-tag');
  expect(footer.textContent).toContain('illustrative results are sample data');
  expect(footer.textContent).toContain('recorded live run is saved evidence');
  expect(footer.textContent).toContain('not sample data or a run happening now');
  expect(tag.title).toContain('recorded live run is saved evidence');
  expect(tag.title).toContain('not account activity');
  expect(screen.getByTestId('recorded-live-run').textContent).toContain('not simulated');
});

it('states the recorded run did not prove new tests failed before the patch', () => {
  render(<RecordedLiveRun />);
  const panel = screen.getByTestId('recorded-live-run');
  expect(panel.textContent).toContain('not run on the unpatched snapshot');
  expect(panel.textContent).toContain('does not establish red-to-green proof');
});
