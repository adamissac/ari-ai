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
  expect(screen.getByTestId('live-defense-api-coverage').textContent).toContain('Live-defense incident machine');
  expect(screen.getByTestId('live-defense-api-coverage').textContent).toContain('/projects/{id}/live-policy-decisions');
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

const SHADOW_DECISION = {
  id: 'lpd_12345678',
  project_id: 'prj_12345678',
  application_id: null,
  created_at: '2026-10-22T20:00:00Z',
  window_end: '2026-10-22T20:00:00Z',
  telemetry_source: 'owned_staging' as const,
  simulated: false,
  producer: 'rules' as const,
  rules_ran: true,
  inference_ran: false,
  inference_status: 'skipped_unavailable' as const,
  action: 'raise_monitoring' as const,
  node: 'payments' as const,
  top_actions: null,
  q_margin: null,
  observation: null,
  policy_version: null,
  checkpoint_sha256: null,
  abstention_reason: 'frozen v6 runner unavailable',
  observation_complete: true,
  feature_schema_ok: false,
  action_mask_valid: false,
  freshness_ok: true,
  authorization_context: 'unverified' as const,
  enforcement: 'NOT_EXECUTED' as const,
  executed: false as const,
  evidence_event_ids: [],
  rule_hits: ['repeated_auth_failures'],
  principal_targets: [],
  feature_mapping_note: null,
  caveat: 'Shadow recommendation from authenticated staging telemetry. Not executed.',
};

const readyDecisions = {
  status: 'ready' as const,
  data: { items: [SHADOW_DECISION], label: 'shadow decisions; enforcement NOT_EXECUTED' },
  error: undefined,
  reload: () => {},
};

it('shows authenticated shadow decisions as NOT EXECUTED, not sample layout', () => {
  render(<LiveOverview mode="live" projectId="prj_1" decisions={readyDecisions} />);
  expect(screen.getByTestId('live-defense-summary').textContent).toContain('none executed');
  const card = screen.getByTestId('live-defense-decision-lpd_12345678');
  expect(card.textContent).toMatch(/NOT EXECUTED/);
  expect(card.textContent).toMatch(/authenticated/);
  expect(card.textContent).not.toMatch(/SAMPLE LAYOUT/i);
  expect(screen.queryByRole('button', { name: /^(apply|isolate|rate-limit|block)$/i })).toBeNull();
});

it('explains a live shadow decision without synthesizing Q-values', () => {
  render(<Explainability mode="live" decisions={readyDecisions} />);
  const card = screen.getByTestId('live-defense-decision-lpd_12345678');
  expect(card.textContent).toMatch(/NOT EXECUTED/);
  expect(card.textContent).toMatch(/unavailable \(inference not run\)/);
  expect(card.textContent).toMatch(/Q-values were not synthesized/);
  expect(screen.getByTestId('live-defense-review-lpd_12345678').textContent).toMatch(/does not apply a control/);
});
