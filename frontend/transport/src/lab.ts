import { ProtocolError } from './contracts.js';

/**
 * Defense Lab simulation (`/lab/simulation`): one simulated episode computed by the backend
 * on request. These decoders are strict on purpose: the lab shows a policy's observation,
 * its valid actions, its Q-values and the reward, so a response that is internally
 * inconsistent (a masked action taken, a reward that is not the sum of its components) is
 * rejected instead of drawn.
 */
export const LAB_POLICY_KINDS = ['ddqn_trained', 'ddqn_untrained', 'random', 'noop', 'threshold_rules'] as const;
export type LabPolicyKind = (typeof LAB_POLICY_KINDS)[number];
export type LabPolicySource = 'learned_checkpoint' | 'untrained_network' | 'scripted_baseline';
const SOURCE_OF: Record<LabPolicyKind, LabPolicySource> = {
  ddqn_trained: 'learned_checkpoint', ddqn_untrained: 'untrained_network',
  random: 'scripted_baseline', noop: 'scripted_baseline', threshold_rules: 'scripted_baseline',
};

export interface LabSimulationScenario { name: string; split: 'train' | 'eval'; horizon: number }
export interface LabSimulationCheckpoint { sha256: string; policy_version: string; path: string }
export interface LabSimulationStatus {
  available: boolean;
  unavailable_reason: string | null;
  label: string;
  scenarios: LabSimulationScenario[];
  policies: LabPolicyKind[];
  checkpoint: LabSimulationCheckpoint | null;
}
export interface LabSimulationRequest { scenario: string; policy: LabPolicyKind; episode_seed: number }
export interface LabSimulationPolicy {
  kind: LabPolicyKind;
  source: LabPolicySource;
  description: string;
  policy_version: string | null;
  checkpoint_sha256: string | null;
  training_steps: number | null;
  gradient_updates: number;
  training_seed: number | null;
}
export interface LabSimulationNode { name: string; criticality: number; exposed: boolean; finding_severity: number }
export interface LabSimulationStep {
  t: number;
  observation: number[];
  action_mask: boolean[];
  q_values: number[] | null;
  action: number;
  action_label: string;
  reward: number;
  reward_components: Record<string, number>;
  terminated: boolean;
  truncated: boolean;
  ground_truth_stages: string[];
}
export interface LabSimulationSummary {
  total_return: number;
  steps: number;
  terminated: boolean;
  ever_impact: boolean;
  impact_nodes: string[];
  first_foothold_t: number | null;
  containment_t: number | null;
  action_counts: Record<string, number>;
}
export interface LabSimulationEpisode {
  schema_version: string;
  kind: 'simulation';
  caveat: string;
  env_id: string;
  episode_seed: number;
  scenario: { name: string; split: 'train' | 'eval'; config_hash: string; horizon: number; nodes: LabSimulationNode[]; edges: [string, string][] };
  policy: LabSimulationPolicy;
  feature_names: string[];
  action_labels: string[];
  reward_component_names: string[];
  steps: LabSimulationStep[];
  final_observation: number[];
  summary: LabSimulationSummary;
}
export interface LabSimulationResult { label: string; episode: LabSimulationEpisode }

const bad = (what: string): never => { throw new ProtocolError(`Invalid lab simulation: ${what}`); };
const rec = (v: unknown, what: string): Record<string, unknown> =>
  (v && typeof v === 'object' && !Array.isArray(v) ? v as Record<string, unknown> : bad(what));
const str = (v: unknown, what: string, max = 400): string =>
  (typeof v === 'string' && v.length > 0 && v.length <= max ? v : bad(what));
const num = (v: unknown, what: string): number => (typeof v === 'number' && Number.isFinite(v) ? v : bad(what));
const int = (v: unknown, what: string): number => (Number.isSafeInteger(v) && (v as number) >= 0 ? v as number : bad(what));
const bool = (v: unknown, what: string): boolean => (typeof v === 'boolean' ? v : bad(what));
const arr = (v: unknown, what: string, max: number): unknown[] => (Array.isArray(v) && v.length <= max ? v : bad(what));
const nullable = <T>(v: unknown, f: (v: unknown, what: string) => T, what: string): T | null => (v === null ? null : f(v, what));
const sha = (v: unknown, what: string): string => (typeof v === 'string' && /^[0-9a-f]{64}$/.test(v) ? v : bad(what));
const split = (v: unknown): 'train' | 'eval' => (v === 'train' || v === 'eval' ? v : bad('scenario split'));
const kind = (v: unknown): LabPolicyKind =>
  (typeof v === 'string' && (LAB_POLICY_KINDS as readonly string[]).includes(v) ? v as LabPolicyKind : bad('policy kind'));
const numberMap = (v: unknown, what: string): Record<string, number> => {
  const r = rec(v, what);
  for (const k of Object.keys(r)) num(r[k], what);
  return r as Record<string, number>;
};

export function decodeLabSimulationStatus(value: unknown): LabSimulationStatus {
  const r = rec(value, 'status');
  const available = bool(r.available, 'available');
  const reason = nullable(r.unavailable_reason, str, 'unavailable_reason');
  const scenarios = arr(r.scenarios, 'scenarios', 100).map(s => {
    const o = rec(s, 'scenario');
    return { name: str(o.name, 'scenario name', 80), split: split(o.split), horizon: int(o.horizon, 'horizon') };
  });
  const policies = arr(r.policies, 'policies', LAB_POLICY_KINDS.length).map(kind);
  const c = r.checkpoint === null ? null : rec(r.checkpoint, 'checkpoint');
  const checkpoint = c && { sha256: sha(c.sha256, 'checkpoint sha256'), policy_version: str(c.policy_version, 'policy_version'), path: str(c.path, 'checkpoint path') };
  // Never both: an unavailable engine must not also offer something to run.
  if (available ? reason !== null || !checkpoint || !scenarios.length || !policies.length : reason === null || scenarios.length > 0) bad('availability is inconsistent');
  return { available, unavailable_reason: reason, label: str(r.label, 'label'), scenarios, policies, checkpoint };
}

export function decodeLabSimulationResult(value: unknown, request: LabSimulationRequest): LabSimulationResult {
  const outer = rec(value, 'result');
  const e = rec(outer.episode, 'episode');
  if (e.kind !== 'simulation') bad('episode is not labelled a simulation');
  const sc = rec(e.scenario, 'scenario');
  const p = rec(e.policy, 'policy');
  const policy: LabSimulationPolicy = {
    kind: kind(p.kind),
    source: p.source === SOURCE_OF[kind(p.kind)] ? p.source as LabPolicySource : bad('policy source does not match its kind'),
    description: str(p.description, 'policy description'),
    policy_version: nullable(p.policy_version, str, 'policy_version'),
    checkpoint_sha256: nullable(p.checkpoint_sha256, sha, 'checkpoint_sha256'),
    training_steps: nullable(p.training_steps, int, 'training_steps'),
    gradient_updates: int(p.gradient_updates, 'gradient_updates'),
    training_seed: nullable(p.training_seed, int, 'training_seed'),
  };
  // A policy is "learned" only with a checkpoint digest and real updates behind it.
  if ((policy.source === 'learned_checkpoint') !== (policy.checkpoint_sha256 !== null && policy.gradient_updates > 0)) bad('learned policy without checkpoint provenance');
  if (policy.source !== 'learned_checkpoint' && policy.gradient_updates !== 0) bad('unlearned policy reports gradient updates');
  const features = arr(e.feature_names, 'feature_names', 256).map(f => str(f, 'feature name', 80));
  const actions = arr(e.action_labels, 'action_labels', 256).map(a => str(a, 'action label', 80));
  const components = arr(e.reward_component_names, 'reward_component_names', 32).map(c => str(c, 'reward component', 80));
  const nodes = arr(sc.nodes, 'nodes', 32).map(n => {
    const o = rec(n, 'node');
    return { name: str(o.name, 'node name', 40), criticality: num(o.criticality, 'criticality'), exposed: bool(o.exposed, 'exposed'), finding_severity: num(o.finding_severity, 'finding_severity') };
  });
  const horizon = int(sc.horizon, 'horizon');
  const observation = (v: unknown, what: string): number[] => {
    const o = arr(v, what, features.length).map(x => num(x, what));
    if (o.length !== features.length || o.some(x => x < 0 || x > 1)) bad(`${what} does not match the feature layout`);
    return o;
  };
  const learned = policy.source !== 'scripted_baseline';
  const steps = arr(e.steps, 'steps', horizon).map((raw, i): LabSimulationStep => {
    const s = rec(raw, 'step');
    const mask = arr(s.action_mask, 'action_mask', actions.length).map(x => bool(x, 'action_mask'));
    const action = int(s.action, 'action');
    const q = s.q_values === null ? null : arr(s.q_values, 'q_values', actions.length).map(x => num(x, 'q_values'));
    const rc = numberMap(s.reward_components, 'reward_components');
    const reward = num(s.reward, 'reward');
    if (int(s.t, 't') !== i) bad('steps are not consecutive');
    if (mask.length !== actions.length || !mask[action]) bad('action is not valid under its mask');
    if (str(s.action_label, 'action_label', 80) !== actions[action]) bad('action label does not match the action');
    if (learned !== (q !== null) || (q && q.length !== actions.length)) bad('Q-values do not match the policy source');
    if (Object.keys(rc).length !== components.length || components.some(c => !(c in rc))) bad('reward components are incomplete');
    if (Math.abs(components.reduce((sum, c) => sum + rc[c]!, 0) - reward) > 1e-6) bad('reward is not the sum of its components');
    const stages = arr(s.ground_truth_stages, 'ground_truth_stages', nodes.length).map(x => str(x, 'stage', 20));
    if (stages.length !== nodes.length) bad('ground truth does not cover every node');
    return { t: i, observation: observation(s.observation, 'observation'), action_mask: mask, q_values: q, action, action_label: actions[action]!, reward, reward_components: rc, terminated: bool(s.terminated, 'terminated'), truncated: bool(s.truncated, 'truncated'), ground_truth_stages: stages };
  });
  const m = rec(e.summary, 'summary');
  const summary: LabSimulationSummary = {
    total_return: num(m.total_return, 'total_return'),
    steps: int(m.steps, 'summary steps'),
    terminated: bool(m.terminated, 'summary terminated'),
    ever_impact: bool(m.ever_impact, 'ever_impact'),
    impact_nodes: arr(m.impact_nodes, 'impact_nodes', nodes.length).map(x => str(x, 'impact node', 40)),
    first_foothold_t: nullable(m.first_foothold_t, int, 'first_foothold_t'),
    containment_t: nullable(m.containment_t, int, 'containment_t'),
    action_counts: numberMap(m.action_counts, 'action_counts'),
  };
  if (!steps.length || summary.steps !== steps.length) bad('summary does not match the steps');
  if (Math.abs(steps.reduce((sum, s) => sum + s.reward, 0) - summary.total_return) > 1e-6) bad('return is not the sum of the rewards');
  const episode: LabSimulationEpisode = {
    schema_version: str(e.schema_version, 'schema_version', 20),
    kind: 'simulation',
    caveat: str(e.caveat, 'caveat'),
    env_id: str(e.env_id, 'env_id', 80),
    episode_seed: int(e.episode_seed, 'episode_seed'),
    scenario: {
      name: str(sc.name, 'scenario name', 80), split: split(sc.split), config_hash: str(sc.config_hash, 'config_hash', 64), horizon, nodes,
      edges: arr(sc.edges, 'edges', 256).map(x => { const pair = arr(x, 'edge', 2); return [str(pair[0], 'edge', 40), str(pair[1], 'edge', 40)] as [string, string]; }),
    },
    policy, feature_names: features, action_labels: actions, reward_component_names: components, steps,
    final_observation: observation(e.final_observation, 'final_observation'),
    summary,
  };
  // The answer must be for the question that was asked.
  if (episode.scenario.name !== request.scenario || policy.kind !== request.policy || episode.episode_seed !== request.episode_seed) bad('episode does not match the request');
  return { label: str(outer.label, 'label'), episode };
}
