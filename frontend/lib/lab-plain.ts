import type { DefenseLabBundle, HiddenStage, LabEpisode } from './lab-types';

/** Plain names for the bundle's policies; unknown ids fall back to the raw id. */
export const POLICY_NAME: Record<string, { name: string; note: string }> = {
  ddqn: { name: 'Trained AI defender', note: 'Learned by trial and error in the simulation (Double DQN).' },
  threshold_rules: { name: 'Simple rules', note: 'Acts when an alert crosses a fixed threshold.' },
  random: { name: 'Random actions', note: 'Picks actions at random. A sanity baseline.' },
  noop: { name: 'Does nothing', note: 'Never acts. Shows what happens with no defense.' },
};
export const policyName = (id: string): string => POLICY_NAME[id]?.name ?? id;

/**
 * Scoreboard rows in plain words. Rates in the bundle are fractions; they are shown
 * as percentages of the same value (×100), with the bundle's 95% interval.
 */
export interface ScoreMetric { key: string; title: string; higherIsBetter: boolean; percent: boolean; explain: string }
export const SCORE_METRICS: readonly ScoreMetric[] = [
  { key: 'compromise_rate', title: 'Attacks that reached their goal', higherIsBetter: false, percent: true, explain: 'Share of simulated episodes where the attacker reached a critical machine.' },
  { key: 'service_uptime', title: 'Time services stayed available', higherIsBetter: true, percent: true, explain: 'Share of time steps where services were not cut off by the defender.' },
  { key: 'false_disruption_rate', title: 'Disruptions aimed at a healthy machine', higherIsBetter: false, percent: true, explain: 'Of the defender\'s disruptive actions (isolate, rate-limit), the share aimed at a machine the attacker had not touched.' },
  { key: 'time_to_containment', title: 'Steps until the attack was contained', higherIsBetter: false, percent: false, explain: 'Average number of time steps before the attack was stopped.' },
];

export interface ScoreCell { policy: string; value: number | null; lo: number | null; hi: number | null; best: boolean }

export function scoreboard(bundle: DefenseLabBundle, metric: ScoreMetric): ScoreCell[] {
  const scale = metric.percent ? 100 : 1;
  const cells = bundle.metrics.map(m => {
    const ci = m.pooled[metric.key];
    const s = (x: number | null | undefined) => (x === null || x === undefined || !Number.isFinite(x) ? null : x * scale);
    return { policy: m.policy, value: s(ci?.mean), lo: s(ci?.ci95[0]), hi: s(ci?.ci95[1]), best: false };
  });
  const finite = cells.filter(c => c.value !== null).map(c => c.value as number);
  if (finite.length > 0) {
    const target = metric.higherIsBetter ? Math.max(...finite) : Math.min(...finite);
    for (const c of cells) c.best = c.value === target;
  }
  return cells;
}

const VERB: Record<string, string> = {
  noop: 'Waited and watched',
  raise_monitoring: 'Watched {node} more closely',
  rate_limit: 'Slowed down traffic to {node}',
  isolate: 'Cut {node} off from the network',
  request_reassessment: 'Asked for {node} to be re-checked',
  escalate_to_human: 'Called a person for help',
};

/** "rate_limit:payments" → "Slowed down traffic to payments". */
export function actionInWords(action: string): string {
  const [verb, node] = action.split(':', 2);
  const template = verb ? VERB[verb] : undefined;
  if (!template) return action;
  return template.replace('{node}', node ?? 'a machine');
}

const STAGE_RANK: Record<HiddenStage, number> = { none: 0, foothold: 1, escalated: 2, impact: 3 };
export const STAGE_WORDS: Record<HiddenStage, string> = {
  none: 'not present',
  foothold: 'got a foothold',
  escalated: 'gained more access',
  impact: 'reached its goal',
};

/** Furthest hidden attacker stage at each step (ground truth, replay only) and whether the defender acted. */
export function episodeTimeline(episode: LabEpisode): { stage: HiddenStage; acted: boolean; disruptive: boolean }[] {
  return episode.steps.map(step => {
    let stage: HiddenStage = 'none';
    for (const n of step.nodes) if (STAGE_RANK[n.hidden_stage_ground_truth] > STAGE_RANK[stage]) stage = n.hidden_stage_ground_truth;
    const verb = step.action.split(':', 1)[0] ?? '';
    return { stage, acted: verb !== 'noop', disruptive: verb === 'isolate' || verb === 'rate_limit' };
  });
}

/** One plain sentence about how a recorded episode ended. */
export function episodeOutcome(episode: LabEpisode): string {
  const who = policyName(episode.policy);
  const n = episode.steps.filter(s => !s.action.startsWith('noop')).length;
  const acts = `${n} time${n === 1 ? '' : 's'}`;
  return episode.compromised
    ? `${who}: the simulated attacker reached its goal (${episode.impact_nodes.join(', ') || 'a critical machine'}). The defender acted ${acts} in ${episode.steps.length} steps.`
    : `${who}: the simulated attacker never reached its goal. The defender acted ${acts} in ${episode.steps.length} steps.`;
}

/**
 * Warns when one measure's winner loses badly on another, using only bundle values:
 * the best-uptime policy and its compromise rate.
 */
export function tradeoffNote(bundle: DefenseLabBundle): string | null {
  const uptime = SCORE_METRICS.find(m => m.key === 'service_uptime');
  const compromise = SCORE_METRICS.find(m => m.key === 'compromise_rate');
  if (!uptime || !compromise) return null;
  const best = scoreboard(bundle, uptime).find(c => c.best);
  const lost = best ? scoreboard(bundle, compromise).find(c => c.policy === best.policy)?.value ?? null : null;
  if (!best || lost === null || lost < 50) return null;
  return `No single measure tells the whole story: "${policyName(best.policy)}" has the best uptime, but the attacker reached its goal in ${lost.toFixed(1)}% of its games.`;
}

/** Plain names for the held-out scenarios; unknown names fall back to a de-snaked id. */
export const SCENARIO_WORDS: Record<string, { name: string; note: string }> = {
  eval_aggressive_noisy: { name: 'Loud, aggressive attacker', note: 'Moves fast and sets off many alerts.' },
  eval_shifted_severity: { name: 'Weak spots moved', note: 'The most vulnerable machines differ from training.' },
  eval_stealthy_lowsignal: { name: 'Quiet, stealthy attacker', note: 'Moves slowly and leaves few alerts.' },
};
export const scenarioName = (id: string): string => SCENARIO_WORDS[id]?.name ?? id.replace(/^eval_/, '').replaceAll('_', ' ');

/** Plain names for the eight reward components recorded per step. */
export const REWARD_WORDS: Record<string, string> = {
  invalid_action: 'Invalid moves',
  action_cost: 'Cost of acting',
  escalation_cost: 'Calling a person',
  disruption: 'Disrupting services',
  adversary_progress: 'Attacker progress',
  containment: 'Containing the attacker',
  impact: 'Attack reached its goal',
  terminal: 'End of game',
};
export const rewardWord = (key: string): string => REWARD_WORDS[key] ?? key.replaceAll('_', ' ');

/**
 * One plain sentence comparing the trained defender with the baselines on the two headline
 * measures, using only bundle values. Null when the trained policy or the measures are missing.
 */
export function keyTakeaway(bundle: DefenseLabBundle): string | null {
  const metric = (key: string) => SCORE_METRICS.find(m => m.key === key);
  const compromise = metric('compromise_rate');
  const uptime = metric('service_uptime');
  if (!compromise || !uptime) return null;
  const c = scoreboard(bundle, compromise);
  const u = scoreboard(bundle, uptime);
  const ai = (cells: ScoreCell[]) => cells.find(x => x.policy === 'ddqn')?.value ?? null;
  const other = (cells: ScoreCell[], id: string) => cells.find(x => x.policy === id)?.value ?? null;
  const aiC = ai(c); const aiU = ai(u);
  const noopC = other(c, 'noop'); const rulesU = other(u, 'threshold_rules');
  if (aiC === null || aiU === null) return null;
  const vsNoop = noopC === null ? '' : ` (with no defense: ${noopC.toFixed(1)}%)`;
  const vsRules = rulesU === null ? '' : ` (simple rules: ${rulesU.toFixed(1)}%)`;
  return `The trained AI defender let the attacker reach its goal in ${aiC.toFixed(1)}% of games${vsNoop}, but kept services available ${aiU.toFixed(1)}% of the time${vsRules}.`;
}
