import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('next/navigation', () => ({ usePathname: () => '/projects' }));

import { SiteFooter } from '@/components/site-footer';
import { useMarkAuthStage } from '@/lib/auth-stage-presence';

function SignInScreen() {
  useMarkAuthStage();
  return <div>sign in</div>;
}

afterEach(cleanup);

describe('records footer and sign-in screens', () => {
  it('shows on a records route when no sign-in screen is mounted', () => {
    render(<SiteFooter />);
    expect(screen.getByTestId('site-footer').textContent).toContain('saved records');
  });

  it('uses illustrative-records copy in demo view', () => {
    document.cookie = 'ari_demo_view=1; Path=/';
    render(<SiteFooter />);
    expect(screen.getByTestId('site-footer').textContent).toContain('Demo account: recorded sample records replayed in your browser.');
    document.cookie = 'ari_demo_view=; Max-Age=0; Path=/';
  });

  it('is not rendered at all while a sign-in screen is mounted, and returns after', () => {
    const { rerender } = render(<><SignInScreen /><SiteFooter /></>);
    expect(screen.queryByTestId('site-footer')).toBeNull();
    act(() => rerender(<SiteFooter />));
    expect(screen.getByTestId('site-footer')).toBeTruthy();
  });
});
