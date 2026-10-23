/**
 * Isolated layout-preview fixtures for the Live Defense dashboard.
 * They are never returned by `api()`, never share IDs with control-plane records,
 * and every object carries `source: 'layout-preview'`.
 */
import type { MapNode, MapState } from '@/components/defense-map';
import type { RankedAction } from '@/lib/live-defense';
import { rankQValues } from '@/lib/live-defense';

export const PREVIEW_BANNER =
  'SAMPLE LAYOUT — illustrative fixtures for UI review. Not live telemetry, not a recorded evaluation, and not model confidence.';

export const PREVIEW_STAMP = '2026-01-15T12:00:00Z';

export interface PreviewEvent {
  source: 'layout-preview';
  id: string;
  title: string;
  kind: string;
  simulated: true;
  received_at: string;
  detail: string;
}

export interface PreviewIncident {
  source: 'layout-preview';
  id: string;
  title: string;
  state: string;
  severity: string;
  simulated: true;
  opened_at: string;
  summary: string;
  timeline: { at: string; label: string; note: string }[];
  linked: { events: number; findings: number; recommendations: number };
}

export interface PreviewRecommendation {
  source: 'layout-preview';
  id: string;
  action: string;
  node: string | null;
  policy_version: string;
  q_margin: number;
  top_actions: RankedAction[];
  contributions: { feature: string; node: string | null; delta_margin: number; kind: string }[];
  caveat: string;
  created_at: string;
}

export const PREVIEW_EVENTS: PreviewEvent[] = [
  {
    source: 'layout-preview',
    id: 'layout-preview:event:push',
    title: 'Example GitHub push (sample)',
    kind: 'github push',
    simulated: true,
    received_at: PREVIEW_STAMP,
    detail: 'Illustrative commit range on a sample payments service. No repository was contacted.',
  },
  {
    source: 'layout-preview',
    id: 'layout-preview:event:runtime',
    title: 'Example runtime batch (sample)',
    kind: 'runtime counters',
    simulated: true,
    received_at: PREVIEW_STAMP,
    detail: 'Placeholder counters so the feed layout can be reviewed. Not authenticated ingest.',
  },
];

export const PREVIEW_INCIDENTS: PreviewIncident[] = [
  {
    source: 'layout-preview',
    id: 'layout-preview:incident:auth',
    title: 'Example: repeated authentication failures (sample)',
    state: 'analysis',
    severity: 'medium',
    simulated: true,
    opened_at: PREVIEW_STAMP,
    summary: 'A layout stand-in for an investigation column. The live autonomous DETECTED→EXECUTING machine is not implemented on the API.',
    timeline: [
      { at: PREVIEW_STAMP, label: 'Reported', note: 'Sample opening note. Not a detection.' },
      { at: PREVIEW_STAMP, label: 'Triaged', note: 'Sample human triage. No adapter ran.' },
      { at: PREVIEW_STAMP, label: 'Analysis', note: 'Sample analysis step for the rail layout.' },
    ],
    linked: { events: 1, findings: 0, recommendations: 1 },
  },
];

const previewScores = rankQValues([
  { action: 'raise_monitoring', node: 'payments', q_value: 1.0 },
  { action: 'escalate_to_human', node: null, q_value: 0.5 },
  { action: 'noop', node: null, q_value: 0.1 },
]);

export const PREVIEW_RECOMMENDATIONS: PreviewRecommendation[] = [
  {
    source: 'layout-preview',
    id: 'layout-preview:rec:watch-payments',
    action: 'raise_monitoring',
    node: 'payments',
    policy_version: 'layout-preview / not a checkpoint',
    q_margin: 0.5,
    top_actions: previewScores,
    contributions: [
      { feature: 'anomaly_score', node: 'payments', delta_margin: 0.2, kind: 'signal' },
      { feature: 'exposed', node: 'api', delta_margin: 0.05, kind: 'context' },
      { feature: 'escalations_remaining_fraction', node: null, delta_margin: -0.04, kind: 'global' },
    ],
    caveat: 'Sample ranking so the explainability layout can be reviewed. These are not Q-values from a loaded policy.',
    created_at: PREVIEW_STAMP,
  },
];

export const PREVIEW_NODES: MapNode[] = [
  { id: 'internet', label: 'Internet', kind: 'edge', critical: false },
  { id: 'gateway', label: 'Gateway', kind: 'edge', critical: false },
  { id: 'api', label: 'API', kind: 'app', critical: false },
  { id: 'auth', label: 'Identity', kind: 'identity', critical: true },
  { id: 'payments', label: 'Payments', kind: 'app', critical: true },
  { id: 'db', label: 'Database', kind: 'data', critical: true },
];

export const PREVIEW_LINKS: [string, string][] = [
  ['internet', 'gateway'],
  ['gateway', 'api'],
  ['gateway', 'auth'],
  ['api', 'payments'],
  ['api', 'db'],
  ['auth', 'payments'],
];

export const PREVIEW_STATES: Record<string, MapState> = {
  internet: 'healthy',
  gateway: 'checking',
  api: 'healthy',
  auth: 'attention',
  payments: 'attention',
  db: 'healthy',
};

export function previewIncident(id: string): PreviewIncident | undefined {
  return PREVIEW_INCIDENTS.find(item => item.id === id);
}

export function previewRecommendation(id: string): PreviewRecommendation | undefined {
  return PREVIEW_RECOMMENDATIONS.find(item => item.id === id);
}
