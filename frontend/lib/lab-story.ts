/**
 * Plain-language model of a recorded Defense Lab episode. Everything here is derived only
 * from values in the evaluation bundle (observations, actions, rewards). Where the bundle
 * cannot explain something (for example *why* the policy chose an action), the text says so
 * instead of inventing reasons. Action meanings follow rl-defense/rl_defense/envs/defense_sim.py.
 */
import type { LabEpisode, LabNodeState, LabScenario, LabStep } from './lab-types';
import { rewardWord } from './lab-plain';

/* ---------- services ---------- */

export type ServiceKind = 'internet' | 'gateway' | 'api' | 'auth' | 'payments' | 'database' | 'web' | 'monitoring' | 'service';

export interface ServiceInfo { kind: ServiceKind; label: string; role: string }

const KINDS: Array<[RegExp, ServiceInfo]> = [
  [/gateway|edge|proxy|lb/, { kind: 'gateway', label: 'Gateway', role: 'The front door: it receives traffic from the internet and passes it inside.' }],
  [/auth|identity|login|sso/, { kind: 'auth', label: 'Sign-in service', role: 'Checks who users are and what they are allowed to do.' }],
  [/pay|billing|ledger/, { kind: 'payments', label: 'Payments', role: 'Handles money: charges, refunds and payment records.' }],
  [/db|database|data|store/, { kind: 'database', label: 'Database', role: 'Stores the company’s most important data. The attacker’s final target.' }],
  [/api|app|backend/, { kind: 'api', label: 'API server', role: 'The application’s main logic. Other services talk through it.' }],
  [/web|site|frontend/, { kind: 'web', label: 'Website', role: 'The pages customers see.' }],
  [/log|monitor|siem/, { kind: 'monitoring', label: 'Monitoring', role: 'Collects logs and alerts.' }],
];

export function serviceInfo(name: string): ServiceInfo {
  const n = name.toLowerCase();
  for (const [re, info] of KINDS) if (re.test(n)) return info;
  return { kind: 'service', label: name, role: 'A service in the test network.' };
}

export const INTERNET: ServiceInfo = { kind: 'internet', label: 'Internet', role: 'Outside traffic. Services marked internet-exposed can be reached from here.' };

/* ---------- node state (observed only) ---------- */

/** Display bands for observed signals (0–1). A presentation choice, stated in the legend. */
export const SIGNAL_BANDS = { elevated: 0.3, high: 0.6 } as const;
export type SignalLevel = 'quiet' | 'elevated' | 'high' | 'unknown';

export function signalValue(s: LabNodeState | undefined): number | null {
  return s ? Math.max(s.alert_rate, s.anomaly_score) : null;
}

export function signalLevel(s: LabNodeState | undefined): SignalLevel {
  const v = signalValue(s);
  if (v === null) return 'unknown';
  return v >= SIGNAL_BANDS.high ? 'high' : v >= SIGNAL_BANDS.elevated ? 'elevated' : 'quiet';
}

export const SIGNAL_WORDS: Record<SignalLevel, string> = {
  quiet: 'No unusual signal',
  elevated: 'Elevated activity',
  high: 'Suspicious activity',
  unknown: 'No data',
};

export interface NodeView {
  name: string;
  info: ServiceInfo;
  critical: boolean;
  exposed: boolean;
  signal: SignalLevel;
  value: number | null;
  watching: boolean;
  rateLimited: boolean;
  isolated: boolean;
  recheck: boolean;
}

export function nodeViews(scenario: LabScenario, states: LabNodeState[]): NodeView[] {
  const by = new Map(states.map(s => [s.node, s]));
  return scenario.nodes.map(n => {
    const s = by.get(n.name);
    return {
      name: n.name,
      info: serviceInfo(n.name),
      critical: n.criticality >= 0.8,
      exposed: n.exposed,
      signal: signalLevel(s),
      value: signalValue(s),
      watching: (s?.monitoring_level ?? 0) > 0,
      rateLimited: !!s?.rate_limited,
      isolated: !!s?.isolated,
      recheck: !!s?.reassessment_pending,
    };
  });
}

/** One short status line for a node, e.g. "Suspicious activity · cut off · watched closely". */
export function nodeStatusLine(v: NodeView): string {
  const parts = [SIGNAL_WORDS[v.signal]];
  if (v.isolated) parts.push('cut off');
  else if (v.rateLimited) parts.push('traffic slowed');
  if (v.watching) parts.push('watched closely');
  if (v.recheck) parts.push('re-check requested');
  return parts.join(' · ');
}

/* ---------- actions ---------- */

export interface ParsedAction { verb: string; node: string | null }
export function parseAction(action: string): ParsedAction {
  const [verb = 'noop', node] = action.split(':', 2);
  return { verb, node: node ?? null };
}

const DISRUPTIVE = new Set(['isolate', 'rate_limit']);
export const isDisruptive = (verb: string) => DISRUPTIVE.has(verb);

/** What the action does in the simulator, in plain words (true to defense_sim.py). */
export function actionMeaning(action: string, labelOf: (node: string) => string = n => n): { did: string; tradeoff: string | null } {
  const { verb, node } = parseAction(action);
  const svc = node ? labelOf(node) : 'a service';
  switch (verb) {
    case 'raise_monitoring': return { did: `The AI started watching ${svc} more closely, so attacker activity there shows up more clearly.`, tradeoff: 'No disruption to users.' };
    case 'rate_limit': return { did: `The AI slowed down traffic to ${svc}, which slows an attacker there for a while.`, tradeoff: `${svc} runs slower for users while this lasts.` };
    case 'isolate': return { did: `The AI cut ${svc} off from the rest of the network, so a threat there cannot spread and may be removed.`, tradeoff: `${svc} is unavailable to users while it is cut off.` };
    case 'request_reassessment': return { did: `The AI asked for ${svc} to be re-checked. After a delay, its known weak spots get fixed.`, tradeoff: 'No disruption; the fix takes a few steps to arrive.' };
    case 'escalate_to_human': return { did: 'The AI asked a person to step in and review.', tradeoff: 'Uses one of a limited number of human escalations.' };
    case 'noop': return { did: 'The AI took no action and kept watching.', tradeoff: null };
    default: return { did: `The AI chose “${action}”.`, tradeoff: null };
  }
}

export const ACTION_SHORT: Record<string, string> = {
  noop: 'Watched',
  raise_monitoring: 'Watch closely',
  rate_limit: 'Slow traffic',
  isolate: 'Cut off',
  request_reassessment: 'Re-check',
  escalate_to_human: 'Call a person',
};

/* ---------- key moments (events) ---------- */

export type MomentKind = 'signal' | 'action' | 'disruptive' | 'end';
export interface Moment { t: number; kind: MomentKind; node: string | null; text: string }

/**
 * Meaningful moments in the recording: a service's signal first turning suspicious, the
 * defender's non-trivial actions, and the end of the game. Derived only from recorded data.
 */
export function keyMoments(episode: LabEpisode, scenario: LabScenario): Moment[] {
  const label = (n: string) => serviceInfo(n).label;
  const out: Moment[] = [];
  let prevLevel = new Map<string, SignalLevel>();
  episode.steps.forEach((step, i) => {
    const t = step.t ?? i;
    for (const s of step.nodes) {
      const lvl = signalLevel(s);
      if (lvl === 'high' && prevLevel.get(s.node) !== 'high') out.push({ t, kind: 'signal', node: s.node, text: `Suspicious activity at ${label(s.node)}` });
    }
    prevLevel = new Map(step.nodes.map(s => [s.node, signalLevel(s)]));
    const a = parseAction(step.action);
    if (a.verb !== 'noop') out.push({ t, kind: isDisruptive(a.verb) ? 'disruptive' : 'action', node: a.node, text: `AI: ${ACTION_SHORT[a.verb] ?? a.verb}${a.node ? ` ${label(a.node)}` : ''}` });
  });
  const last = episode.steps.at(-1);
  if (last) out.push({ t: last.t ?? episode.steps.length - 1, kind: 'end', node: null, text: episode.compromised ? 'Evaluation complete: the attacker reached its goal' : 'Evaluation complete: the attacker never reached its goal' });
  void scenario;
  return out;
}

/**
 * The story beats worth jumping to, in time order: every service first turning suspicious, the
 * first time each kind of action is taken, the first cut-off of each service, then the end.
 * A defender that acts every few steps would otherwise fill the list with routine moves.
 */
export function storyMoments(moments: Moment[], limit = 8): Moment[] {
  const end = moments.filter(m => m.kind === 'end');
  const body = moments.filter(m => m.kind !== 'end');
  const verbOf = (m: Moment) => m.text.replace(/^AI: /, '').replace(m.node ? ` ${serviceInfo(m.node).label}` : '', '');
  const picked: Moment[] = [];
  const take = (m: Moment) => { if (!picked.includes(m)) picked.push(m); };
  const firstSignal = new Set<string>();
  for (const m of body) if (m.kind === 'signal' && m.node && !firstSignal.has(m.node)) { firstSignal.add(m.node); take(m); }
  const firstVerb = new Set<string>();
  for (const m of body) if (m.kind !== 'signal' && !firstVerb.has(verbOf(m))) { firstVerb.add(verbOf(m)); take(m); }
  const firstCut = new Set<string>();
  for (const m of body) if (m.kind === 'disruptive' && verbOf(m) === ACTION_SHORT.isolate && m.node && !firstCut.has(m.node)) { firstCut.add(m.node); take(m); }
  const room = Math.max(0, limit - end.length);
  return [...picked.sort((x, y) => x.t - y.t).slice(0, room), ...end];
}

/* ---------- narrative for one step ---------- */

export interface StepStory {
  now: string;
  did: string;
  tradeoff: string | null;
  why: string;
  effect: string | null;
  cost: string;
  target: string | null;
}

const fmt = (v: number) => v.toFixed(2);

export function stepStory(episode: LabEpisode, scenario: LabScenario, t: number): StepStory {
  const steps = episode.steps;
  const step = steps[Math.max(0, Math.min(t, steps.length - 1))] as LabStep | undefined;
  const label = (n: string) => serviceInfo(n).label;
  if (!step) return { now: 'No recorded step.', did: '—', tradeoff: null, why: '', effect: null, cost: '', target: null };
  const views = nodeViews(scenario, step.nodes);
  const hot = views.filter(v => v.signal === 'high');
  const warm = views.filter(v => v.signal === 'elevated');
  const top = [...views].sort((a, b) => (b.value ?? 0) - (a.value ?? 0))[0];
  const now = hot.length
    ? `Suspicious activity at ${hot.map(v => `${label(v.name)} (${fmt(v.value ?? 0)})`).join(', ')}.`
    : warm.length
      ? `Activity is elevated at ${warm.map(v => `${label(v.name)} (${fmt(v.value ?? 0)})`).join(', ')}.`
      : `Signals are quiet across all ${views.length} services.`;

  const a = parseAction(step.action);
  const meaning = actionMeaning(step.action, label);
  let why: string;
  if (a.verb === 'noop') why = 'The recording does not include the policy’s reasoning. It held off this step.';
  else if (!a.node) why = 'The recording does not include the policy’s reasoning.';
  else if (top && top.name === a.node && (top.value ?? 0) >= SIGNAL_BANDS.elevated) why = `The recording does not include the policy’s reasoning, but it acted on the service with the strongest signal it could see (${label(a.node)}, ${fmt(top.value ?? 0)}).`;
  else if (top && (top.value ?? 0) >= SIGNAL_BANDS.elevated) why = `The recording does not include the policy’s reasoning. Note: the strongest signal it could see was at ${label(top.name)} (${fmt(top.value ?? 0)}), not ${label(a.node)}.`;
  else why = 'The recording does not include the policy’s reasoning. Signals were quiet when it acted.';

  // Effect: compare the target's observed state before and after, and a few steps later.
  let effect: string | null = null;
  if (a.node && a.verb !== 'noop') {
    const after = steps[t + 1]?.nodes.find(s => s.node === a.node);
    const before = step.nodes.find(s => s.node === a.node);
    const later = steps[Math.min(steps.length - 1, t + 5)]?.nodes.find(s => s.node === a.node);
    const changes: string[] = [];
    if (after && before) {
      if (after.isolated && !before.isolated) changes.push(`${label(a.node)} is now cut off`);
      if (after.rate_limited && !before.rate_limited) changes.push(`traffic to ${label(a.node)} is now slowed`);
      if (after.monitoring_level > before.monitoring_level) changes.push(`${label(a.node)} is now watched closely`);
      if (after.reassessment_pending && !before.reassessment_pending) changes.push(`a re-check of ${label(a.node)} is pending`);
    }
    const b = signalValue(before); const l = signalValue(later);
    if (b !== null && l !== null && t + 5 < steps.length) {
      const dir = l < b - 0.05 ? 'dropped' : l > b + 0.05 ? 'rose' : 'stayed about the same';
      changes.push(`five steps later its signal ${dir} (${fmt(b)} → ${fmt(l)})`);
    }
    effect = changes.length ? `${changes[0]!.charAt(0).toUpperCase()}${changes[0]!.slice(1)}${changes.length > 1 ? `; ${changes.slice(1).join('; ')}` : ''}.` : null;
  }

  const comps = Object.entries(step.reward_components).filter(([, v]) => v < 0).sort((x, y) => x[1] - y[1]);
  const cost = step.reward < 0 && comps[0]
    ? `This step cost the defender ${fmt(Math.abs(step.reward))} points, mostly from “${rewardWord(comps[0][0]).toLowerCase()}”.`
    : step.reward > 0 ? `This step earned the defender ${fmt(step.reward)} points.` : 'This step had no cost.';

  return { now, did: meaning.did, tradeoff: meaning.tradeoff, why, effect, cost, target: a.node };
}

/** Overall status for the header at step t (observed signals only). */
export function overallStatus(scenario: LabScenario, step: LabStep | undefined): { tone: 'quiet' | 'elevated' | 'high'; text: string } {
  const views = nodeViews(scenario, step?.nodes ?? []);
  const hot = views.filter(v => v.signal === 'high').length;
  const warm = views.filter(v => v.signal === 'elevated').length;
  if (hot) return { tone: 'high', text: `Suspicious activity at ${hot} service${hot === 1 ? '' : 's'}` };
  if (warm) return { tone: 'elevated', text: `Elevated activity at ${warm} service${warm === 1 ? '' : 's'}` };
  return { tone: 'quiet', text: 'No unusual signals' };
}

/** Latest non-trivial action at or before t. */
export function latestAction(episode: LabEpisode, t: number): { t: number; action: string } | null {
  for (let i = Math.min(t, episode.steps.length - 1); i >= 0; i--) {
    const s = episode.steps[i];
    if (s && !s.action.startsWith('noop')) return { t: s.t ?? i, action: s.action };
  }
  return null;
}
