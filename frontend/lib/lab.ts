import type { DefenseLabBundle, LabEpisode, LabStep, MetricCI } from './lab-types';

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

const ACTION_PHRASE: Record<string, (node: string | null) => string> = {
  noop: () => 'do nothing',
  escalate_to_human: () => 'escalate to a person',
  isolate: node => `isolate ${node} in this simulation`,
  rate_limit: node => `rate-limit ${node} in this simulation`,
  raise_monitoring: node => `raise monitoring on ${node} in this simulation`,
  request_reassessment: node => `request a reassessment of ${node} in this simulation`,
};

/** What this recorded step shows the defender, without the hidden attacker stage. */
export function stepObservation(step: LabStep | undefined): string {
  if (!step) return 'This step was not recorded.';
  const action = describeAction(step.action);
  if (step.nodes.length === 0) {
    return `This step has no recorded node signals. The recorded action is to ${action}. The hidden attacker stage is not shown.`;
  }
  const max = Math.max(...step.nodes.map(node => node.alert_rate));
  const names = step.nodes.filter(node => node.alert_rate === max).map(node => node.node);
  const where = names.length === 1 ? names[0]! : names.join(', ');
  return `The highest recorded alert rate at this step is ${formatRate(max)} on ${where}. The recorded action is to ${action}. This uses recorded signals, not the hidden attacker stage.`;
}

function describeAction(action: string): string {
  const [verb, node] = action.split(':', 2);
  const phrase = verb ? ACTION_PHRASE[verb] : undefined;
  if (!phrase || (verb !== 'noop' && verb !== 'escalate_to_human' && !node)) {
    return `follow the recorded action ${action}`;
  }
  return phrase(node ?? null);
}

function formatRate(value: number): string {
  if (!Number.isFinite(value)) return 'unrecorded';
  return value.toFixed(3).replace(/0+$/, '').replace(/\.$/, '');
}

/** One sentence from a recorded episode. It does not describe a live network. */
export function episodeStory(episode: LabEpisode): string {
  const first = episode.steps[0];
  const last = episode.steps[episode.steps.length - 1];
  if (!first || !last) return 'This recording has no steps.';
  const outcome = episode.compromised ? 'The recording is marked compromised.' : 'The recording is marked contained.';
  const impact = episode.impact_nodes.length === 0
    ? 'No node is recorded as reaching impact.'
    : `Impact is recorded on ${episode.impact_nodes.join(', ')}.`;
  return `First recorded action: ${first.action}. Last recorded action: ${last.action}. ${outcome} ${impact} This is one simulated episode, not a live network.`;
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
