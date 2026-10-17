import type { DefenseLabBundle, LabEpisode, MetricCI } from './lab-types';

/** Metrics where a larger value is better; everything else is a cost. */
export const HIGHER_IS_BETTER = new Set(['return', 'service_uptime']);

export const METRIC_LABEL: Record<string, string> = {
  return: 'Episode return',
  compromise_rate: 'Compromise rate',
  time_to_containment: 'Time to containment (steps)',
  false_disruption_rate: 'False disruption rate',
  escalations: 'Escalations per episode',
  action_cost: 'Action cost',
  service_uptime: 'Service uptime',
  invalid_actions: 'Invalid actions',
};

export interface MetricRow { policy: string; mean: number | null; lo: number | null; hi: number | null }

export function metricRows(bundle: DefenseLabBundle, metric: string, scenario: string | null): MetricRow[] {
  return bundle.metrics.map(m => {
    const ci: MetricCI | undefined = scenario ? m.per_scenario[scenario]?.[metric] : m.pooled[metric];
    return { policy: m.policy, mean: ci?.mean ?? null, lo: ci?.ci95[0] ?? null, hi: ci?.ci95[1] ?? null };
  });
}

export function metricNames(bundle: DefenseLabBundle): string[] {
  const names = new Set<string>();
  for (const m of bundle.metrics) for (const k of Object.keys(m.pooled)) names.add(k);
  return [...names];
}

/** Evaluation episodes behind each pooled number: seeds × episodes × held-out scenarios. */
export function sampleSize(bundle: DefenseLabBundle, scenario: string | null): number {
  const perScenario = bundle.training_seeds.length * bundle.episodes_per_config_per_seed;
  return scenario ? perScenario : perScenario * bundle.scenarios.length;
}

/** Linear scale over every finite mean/CI bound so error bars share one axis. */
export function domain(rows: MetricRow[]): [number, number] {
  const values = rows.flatMap(r => [r.mean, r.lo, r.hi]).filter((x): x is number => x !== null && Number.isFinite(x));
  if (values.length === 0) return [0, 1];
  let min = Math.min(0, ...values);
  let max = Math.max(0, ...values);
  if (min === max) { min -= 1; max += 1; }
  return [min, max];
}

export function rewardTotals(episode: LabEpisode, upTo = episode.steps.length): Record<string, number> {
  const totals: Record<string, number> = {};
  for (const step of episode.steps.slice(0, upTo)) {
    for (const [k, v] of Object.entries(step.reward_components)) totals[k] = (totals[k] ?? 0) + v;
  }
  return totals;
}

export function cumulativeReturn(episode: LabEpisode, upTo: number): number {
  return episode.steps.slice(0, upTo).reduce((s, x) => s + x.reward, 0);
}

export function episodeLabel(e: LabEpisode): string {
  return `${e.policy} · ${e.scenario} · episode seed ${e.episode_seed}${e.training_seed !== null ? ` · training seed ${e.training_seed}` : ''}`;
}
