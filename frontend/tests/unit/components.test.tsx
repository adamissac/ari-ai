import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { DiffView } from '@/components/diff-view';
import { Badge, ErrorState } from '@/components/ui';
import { ASSESSMENT_STATE, FINDING_STATUS } from '@/lib/status';

vi.mock('next/navigation', () => ({ usePathname: () => '/projects', useRouter: () => ({ push: () => undefined }) }));

afterEach(cleanup);

describe('components', () => {
  it('badges render text and status marks', () => {
    const { container } = render(<Badge view={FINDING_STATUS.hypothesis} />);
    expect(screen.getByText('Hypothesis')).toBeTruthy();
    expect(container.querySelector('.status-mark-pending')).toBeTruthy();
  });
  it('draws the done, paused, and failed status marks', () => {
    const { container, rerender } = render(<Badge view={FINDING_STATUS.verified} />);
    expect(container.querySelector('.status-mark-done')).toBeTruthy();
    rerender(<Badge view={ASSESSMENT_STATE.AWAITING_APPROVAL} />);
    expect(container.querySelector('.status-mark-paused')).toBeTruthy();
    rerender(<Badge view={ASSESSMENT_STATE.FAILED} />);
    expect(container.querySelector('.status-mark-failed')?.textContent).toBe('×');
  });
  it('diff content is rendered as text, never as HTML', () => {
    const { container } = render(<DiffView diff={'--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-<b>old</b>\n+<img src=x onerror=alert(1)>\n'} />);
    expect(container.querySelector('img')).toBeNull();
    expect(container.textContent).toContain('<img src=x onerror=alert(1)>');
  });
  it('error state names the failure kind', () => {
    render(<ErrorState error={new TypeError('Failed to fetch')} context="Load" />);
    expect(screen.getByTestId('error-state').textContent).toContain('Backend unreachable');
  });
  it('demo banner appears only with the demo-view cookie', async () => {
    const { DemoBanner } = await import('@/components/demo-banner');
    const { container } = render(<DemoBanner />);
    expect(container.textContent).toBe('');
    cleanup();
    document.cookie = 'ari_demo_view=1; Path=/';
    render(<DemoBanner />);
    expect(screen.getByText('Demo account · Lumen Pay sample data — every repository, commit and result here is illustrative.')).toBeTruthy();
    document.cookie = 'ari_demo_view=; Max-Age=0; Path=/';
  });
});
