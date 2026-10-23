import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ControlsDashboard } from '@/components/live-defense/controls';
import { Explainability } from '@/components/live-defense/explain';
import { InvestigationList } from '@/components/live-defense/investigation';
import { LiveOverview } from '@/components/live-defense/overview';
import { LiveDefenseShell } from '@/components/live-defense/shell';
import { PREVIEW_INCIDENTS } from '@/lib/live-defense-preview';
import { OWNED_TEST_LABEL } from '@/lib/live-defense';

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
  expect(screen.getByTestId('live-defense-api-coverage').textContent).toContain('/control-authorizations');
  expect(screen.getByRole('link', { name: 'Controls' }).getAttribute('href')).toContain('/live-defense/controls');
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

it('keeps sample controls distinct from owned-test enforcement', () => {
  route.path = '/projects/prj_1/live-defense/controls';
  route.preview = 'layout';
  render(
    <LiveDefenseShell projectId="prj_1">
      <ControlsDashboard mode="layout-preview" projectId="prj_1" />
    </LiveDefenseShell>,
  );
  expect(screen.getByTestId('live-defense-preview-controls').textContent).toMatch(/SAMPLE LAYOUT/);
  expect(screen.queryByTestId('live-defense-authorize')).toBeNull();
  expect(screen.queryByRole('button', { name: /^(apply|isolate|rate-limit|block source)$/i })).toBeNull();
});

const LIVE_CONTROL = {
  id: 'lct_12345678',
  project_id: 'prj_12345678',
  application_id: 'app_12345678',
  live_policy_decision_id: null,
  grant_id: 'cgr_12345678',
  kind: 'rate_limit' as const,
  target: { type: 'route' as const, value: 'GET /payments/pay_fixture' },
  duration_s: 60,
  status: 'verified' as const,
  origin: 'analyst' as const,
  binding_sha256: 'a'.repeat(64),
  requested_by: 'usr_12345678',
  requested_at: '2026-10-23T00:00:00Z',
  authorized_at: '2026-10-23T00:00:01Z',
  executing_at: '2026-10-23T00:00:02Z',
  verified_at: '2026-10-23T00:00:03Z',
  expires_at: '2026-10-23T00:01:03Z',
  ended_at: null,
  checks: [],
  verification: {
    observed_effect: true,
    adapter_http_status: 200,
    probe_http_statuses: [200, 429],
    method: 'http_probe',
    detail: 'fixture returned 429 after apply',
    verified_at: '2026-10-23T00:00:03Z',
    adapter_http_200_is_not_effectiveness: true as const,
  },
  unresolved: false,
  simulated: false as const,
  environment_label: 'OWNED TEST ENVIRONMENT' as const,
  caveat: 'Owned-test control. Not customer production.',
  max_requests: 1,
  rationale: 'fixture',
  denial_reason: null,
};

it('labels verified owned-test controls and does not offer isolate', () => {
  route.path = '/projects/prj_1/live-defense/controls';
  render(
    <ControlsDashboard
      mode="live"
      projectId="prj_1"
      apps={{
        status: 'ready',
        data: {
          items: [{
            id: 'app_12345678',
            project_id: 'prj_12345678',
            name: 'payments-lite owned test',
            environment: 'owned_test',
            ingest_configured: true,
            last_ingest_at: null,
            verification: 'unverified',
            shadow_mode: true,
            control_channel_configured: true,
            disconnected_at: null,
            created_by: 'usr_12345678',
            created_at: '2026-10-23T00:00:00Z',
          }],
        },
        error: undefined,
        reload: () => {},
      }}
      controls={{
        status: 'ready',
        data: { items: [LIVE_CONTROL], label: 'OWNED TEST ENVIRONMENT controls' },
        error: undefined,
        reload: () => {},
      }}
    />,
  );
  const card = screen.getByTestId('live-defense-control-lct_12345678');
  expect(card.textContent).toContain(OWNED_TEST_LABEL);
  expect(card.textContent).toMatch(/HTTP 200 is not effectiveness/);
  expect(card.textContent).not.toMatch(/SAMPLE LAYOUT/i);
  expect(screen.getByTestId('live-defense-authorize').textContent).toMatch(/control-authorizations/);
  expect(screen.queryByRole('button', { name: /^(apply|isolate|rate-limit|block)$/i })).toBeNull();
  expect(screen.getByRole('button', { name: 'Authorize owned-test control' })).toBeTruthy();
});

it('explains a live shadow decision without synthesizing Q-values', () => {
  render(<Explainability mode="live" decisions={readyDecisions} />);
  const card = screen.getByTestId('live-defense-decision-lpd_12345678');
  expect(card.textContent).toMatch(/NOT EXECUTED/);
  expect(card.textContent).toMatch(/unavailable \(inference not run\)/);
  expect(card.textContent).toMatch(/Q-values were not synthesized/);
  expect(screen.getByTestId('live-defense-review-lpd_12345678').textContent).toMatch(/does not apply a control/);
});
