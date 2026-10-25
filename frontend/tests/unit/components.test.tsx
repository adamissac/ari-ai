import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { DiffView } from '@/components/diff-view';
import { Badge, ErrorState } from '@/components/ui';
import { FINDING_STATUS } from '@/lib/status';

afterEach(cleanup);

describe('components', () => {
  it('badges render text and glyph', () => {
    render(<Badge view={FINDING_STATUS.hypothesis} />);
    expect(screen.getByText('Hypothesis')).toBeTruthy();
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
  it('fixture mode banner appears only when explicitly enabled', async () => {
    vi.resetModules();
    vi.stubEnv('NEXT_PUBLIC_DEMO_FIXTURES', '');
    const off = await import('@/components/demo-banner');
    const { container } = render(<off.DemoBanner />);
    expect(container.textContent).toBe('');
    cleanup();
    vi.resetModules();
    vi.stubEnv('NEXT_PUBLIC_DEMO_FIXTURES', '1');
    const on = await import('@/components/demo-banner');
    render(<on.DemoBanner />);
    expect(screen.getByRole('status').textContent).toContain('DEMO DATA');
    vi.unstubAllEnvs();
  });
});
