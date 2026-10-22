import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { Explainability } from '@/components/live-defense/explain';
import { InvestigationList } from '@/components/live-defense/investigation';
import { LiveOverview } from '@/components/live-defense/overview';
import { LiveDefenseShell } from '@/components/live-defense/shell';
import { PREVIEW_INCIDENTS } from '@/lib/live-defense-preview';

const route = vi.hoisted(() => ({ path: '/projects/prj_1/live-defense', preview: null as string | null, replaced: '' }));
vi.mock('next/navigation', () => ({
  usePathname: () => route.path,
  useSearchParams: () => new URLSearchParams(route.preview ? `preview=${route.preview}` : ''),
  useRouter: () => ({ replace: (href: string) => { route.replaced = href; } }),
  useParams: () => ({}),
}));

afterEach(() => {
  cleanup();
  route.path = '/projects/prj_1/live-defense';
  route.preview = null;
  route.replaced = '';
});

it('labels sample layout, lists missing APIs, and has no enforcement buttons', () => {
  route.preview = 'layout';
  render(
    <LiveDefenseShell projectId="prj_1">
      <LiveOverview mode="layout-preview" projectId="prj_1" />
    </LiveDefenseShell>,
  );
  expect(screen.getByTestId('live-defense').getAttribute('data-mode')).toBe('layout-preview');
  expect(screen.getByTestId('live-defense-preview-banner').textContent).toMatch(/Not live telemetry/);
  expect(screen.getByTestId('live-defense-no-enforcement').textContent).toMatch(/does not apply, isolate, rate-limit, or block/);
  expect(screen.getByTestId('live-defense-api-coverage').textContent).toContain('Live policy inference stream');
  expect(screen.getByTestId('defense-map').textContent).toMatch(/SAMPLE LAYOUT/);
  expect(screen.queryByRole('button', { name: /^(apply|isolate|rate-limit|block source)$/i })).toBeNull();
});

it('does not draw a live map or claim healthy without recorded checks', () => {
  render(<LiveOverview mode="live" projectId="prj_1" />);
  expect(screen.queryByTestId('defense-map')).toBeNull();
  expect(screen.getByTestId('live-defense-health-unknown').textContent).toMatch(/unknown/);
  expect(screen.getByTestId('live-defense-summary').textContent).not.toMatch(/\bhealthy\b/);
});

it('keeps the standalone pilot on sample layout with no live toggle', () => {
  render(<LiveDefenseShell projectId={null} standalone><p>child</p></LiveDefenseShell>);
  expect(screen.getByTestId('live-defense').getAttribute('data-mode')).toBe('layout-preview');
  expect(screen.getByTestId('live-defense-preview-banner').textContent).toMatch(/Not live telemetry/);
  expect(screen.queryByTestId('live-defense-preview-toggle')).toBeNull();
});

it('toggles layout-preview on the current path', () => {
  render(<LiveDefenseShell projectId="prj_1"><p>child</p></LiveDefenseShell>);
  fireEvent.click(screen.getByTestId('live-defense-preview-toggle'));
  expect(route.replaced).toBe('/projects/prj_1/live-defense?preview=layout');
});

it('marks Q ranking as sample in layout-preview explainability', () => {
  render(<Explainability mode="layout-preview" />);
  const ranking = screen.getByTestId('live-defense-q-ranking');
  expect(ranking.getAttribute('data-sample')).toBe('true');
  expect(screen.getByTestId('live-defense-preview-explain').textContent).toMatch(/not a loaded policy/);
  expect(screen.queryByRole('button', { name: /apply/i })).toBeNull();
});

it('does not call investigation actions from the sample list', () => {
  render(<InvestigationList mode="layout-preview" projectId={null} />);
  const sample = PREVIEW_INCIDENTS[0];
  expect(sample).toBeTruthy();
  const link = screen.getByRole('link', { name: /authentication failures/ });
  expect(link.getAttribute('href')).toContain('/live-defense-pilot/incidents/');
  expect(within(link).queryByRole('button')).toBeNull();
});
