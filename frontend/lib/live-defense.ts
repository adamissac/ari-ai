/**
 * Live Defense dashboard helpers. Live mode reads only control-plane records.
 * Layout-preview samples live in `live-defense-preview.ts` and must never be
 * mixed into a live list or labelled as telemetry.
 */

export type LiveDefenseMode = 'live' | 'layout-preview';

export const PREVIEW_QUERY = 'preview';
export const PREVIEW_VALUE = 'layout';

export const SIMULATION_CAVEAT =
  'Recommendation from a policy trained in an isolated test environment. Not applied automatically.';

export const NO_ENFORCEMENT =
  'This dashboard does not apply, isolate, rate-limit, or block anything. Recommendations stay recommendations until a person acts on the existing Incidents page.';

export function liveDefenseMode(previewParam: string | null | undefined): LiveDefenseMode {
  return previewParam === PREVIEW_VALUE ? 'layout-preview' : 'live';
}

/** Keep the current path and swap only the layout-preview flag. */
export function withLiveDefenseMode(href: string, mode: LiveDefenseMode): string {
  const [path, query = ''] = href.split('?');
  const params = new URLSearchParams(query);
  if (mode === 'layout-preview') params.set(PREVIEW_QUERY, PREVIEW_VALUE);
  else params.delete(PREVIEW_QUERY);
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}

export function liveDefenseHref(projectId: string | null, tab: 'overview' | 'incidents' | 'explain' = 'overview', mode: LiveDefenseMode = 'live'): string {
  const base = projectId === null ? '/live-defense-pilot' : `/projects/${projectId}/live-defense`;
  const path = tab === 'overview' ? base : `${base}/${tab === 'incidents' ? 'incidents' : 'explain'}`;
  return projectId === null ? path : withLiveDefenseMode(path, mode);
}

export type LiveDefenseTab = 'overview' | 'incidents' | 'explain';

export function liveDefenseTab(pathname: string): LiveDefenseTab {
  if (/live-defense(?:-pilot)?\/explain(?:\/|$)/.test(pathname)) return 'explain';
  if (/live-defense(?:-pilot)?\/incidents(?:\/|$)/.test(pathname)) return 'incidents';
  return 'overview';
}

/** Endpoints this UI already consumes. Do not invent siblings. */
export const USED_LIVE_APIS = [
  { method: 'GET', path: '/projects/{id}', use: '24/7 defense switch and project name' },
  { method: 'PATCH', path: '/projects/{id}', use: 'owner toggle of monitoring_policy.enabled' },
  { method: 'GET', path: '/projects/{id}/events', use: 'recorded webhook and runtime events' },
  { method: 'GET', path: '/projects/{id}/reassessments', use: 're-checks those events requested' },
  { method: 'GET', path: '/projects/{id}/incidents', use: 'NIST incident list' },
  { method: 'GET', path: '/incidents/{id}', use: 'incident timeline and linked evidence' },
  { method: 'GET', path: '/projects/{id}/defense-recommendations', use: 'simulation-derived policy suggestions' },
  { method: 'GET', path: '/defense-recommendations/{id}/explanation', use: 'occlusion explanation of one suggestion' },
  { method: 'GET', path: '/projects/{id}/rl-evaluations', use: 'imported held-out evaluation pointers' },
] as const;

/** Capabilities the dashboard needs next. Shown as missing — never filled with live-looking numbers. */
export const MISSING_LIVE_APIS = [
  {
    id: 'connected_apps',
    title: 'Connected applications',
    reason: 'No resource lists owner-registered apps, control URLs, grants, or ingest tokens.',
  },
  {
    id: 'component_health',
    title: 'Component health and topology',
    reason: 'No per-node last-check, healthy/checking state, or dependency graph is served for a project.',
  },
  {
    id: 'live_incidents',
    title: 'Live-defense incident machine',
    reason: 'DETECTED → TRIAGED → RECOMMENDED → AUTHORIZED → EXECUTING → VERIFYING is not an API. Existing incidents stay on the NIST human lifecycle.',
  },
  {
    id: 'live_inference',
    title: 'Live policy inference stream',
    reason: 'Q-values on stored recommendations are simulation-derived snapshots, not a live confidence feed.',
  },
  {
    id: 'worker_heartbeat',
    title: 'Defense worker heartbeat',
    reason: 'No liveness record for the live-defense job worker.',
  },
] as const;

export interface OverviewCounts {
  monitoringEnabled: boolean;
  eventsKnown: boolean;
  eventCount: number;
  simulatedEventCount: number;
  incidentsKnown: boolean;
  openIncidentCount: number;
  simulatedIncidentCount: number;
  recommendationsKnown: boolean;
  recommendationCount: number;
}

export function liveDefenseOverviewCopy(counts: OverviewCounts): string {
  const watch = counts.monitoringEnabled
    ? '24/7 defense is on for this project (repository push re-checks).'
    : '24/7 defense is off for this project.';
  const events = !counts.eventsKnown
    ? 'Recorded events have not loaded.'
    : counts.eventCount === 0
      ? 'No recorded events yet.'
      : `${counts.eventCount} recorded event${counts.eventCount === 1 ? '' : 's'}${counts.simulatedEventCount > 0 ? `, ${counts.simulatedEventCount} labelled simulated` : ''}.`;
  const incidents = !counts.incidentsKnown
    ? 'Incidents have not loaded.'
    : counts.openIncidentCount === 0
      ? 'No open incidents.'
      : `${counts.openIncidentCount} open incident${counts.openIncidentCount === 1 ? '' : 's'}${counts.simulatedIncidentCount > 0 ? `, ${counts.simulatedIncidentCount} labelled synthetic` : ''}.`;
  const recs = !counts.recommendationsKnown
    ? 'Simulation recommendations have not loaded.'
    : counts.recommendationCount === 0
      ? 'No simulation recommendation is stored.'
      : `${counts.recommendationCount} simulation recommendation${counts.recommendationCount === 1 ? '' : 's'} listed; none is applied automatically.`;
  return `${watch} ${events} ${incidents} ${recs} Component health is not in the API, so this page does not draw a live map.`;
}

export interface RankedAction {
  action: string;
  node: string | null;
  q_value: number;
  rank: number;
  /** 0–1 bar length from |q| relative to the largest |q| in the set. */
  bar: number;
}

/** Rank stored Q-values. Empty input stays empty — never invent a confidence score. */
export function rankQValues(actions: readonly { action: string; node: string | null; q_value: number }[]): RankedAction[] {
  if (actions.length === 0) return [];
  const sorted = [...actions].sort((a, b) => b.q_value - a.q_value || a.action.localeCompare(b.action));
  const peak = Math.max(...sorted.map(a => Math.abs(a.q_value)), Number.EPSILON);
  return sorted.map((action, index) => ({
    ...action,
    rank: index + 1,
    bar: Math.abs(action.q_value) / peak,
  }));
}

export function actionInWords(action: string, node: string | null): string {
  const target = node ? ` on ${node}` : '';
  switch (action) {
    case 'noop': return 'Do nothing extra';
    case 'raise_monitoring': return `Watch more closely${target}`;
    case 'rate_limit': return `Slow traffic${target} (not applied)`;
    case 'isolate': return `Isolate${target} (not applied)`;
    case 'request_reassessment': return 'Ask for a re-check';
    case 'escalate_to_human': return 'Escalate to a person';
    case 'block_principal': return 'Block a flagged identity (not applied)';
    case 'block_principal_long': return 'Longer block of a flagged identity (not applied)';
    case 'block_top_principal_long': return 'Longer block of the heaviest flagged identity (not applied)';
    default: return action.replaceAll('_', ' ');
  }
}

export type Sourced<T> = T & { source: LiveDefenseMode };

/** Refuse to render a mixed live + preview collection. */
export function assertSingleSource<T extends { source: LiveDefenseMode }>(items: readonly T[], label: string): LiveDefenseMode | null {
  if (items.length === 0) return null;
  const first = items[0]?.source;
  if (first === undefined) return null;
  if (items.some(item => item.source !== first)) {
    throw new Error(`Live Defense refused to mix live records with layout-preview samples (${label}).`);
  }
  return first;
}

export function isOpenIncidentState(state: string): boolean {
  return state !== 'closed' && state !== 'rejected';
}
