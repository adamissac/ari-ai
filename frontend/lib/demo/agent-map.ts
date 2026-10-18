import type { DemoComponent, DemoRepo } from '@/lib/demo/data';
import type { AgentId, AgentRunView, Analysis, ToolStep } from '@/lib/demo/scenarios';

/**
 * The seven-agent replay as a map: each recorded tool step is pinned to the part of the
 * system it touched, so the page can show which agent is checking which part of the app.
 * Illustrative (ADR 0013): the steps come from the simulated scenario for the commit.
 */

export type Team = AgentRunView['team'];
export const TEAM_COLOR: Record<Team, string> = { Red: '#ff7a5c', Blue: '#6ea8ff', Independent: '#5fd49a' };

export interface Tick {
  agent: AgentId;
  team: Team;
  step: ToolStep;
  index: number;
  component: string;
}

export type ComponentState = 'outside' | 'waiting' | 'checking' | 'scanned' | 'clear' | 'issue' | 'fixed';

/** Plain-language description of a tool step, for people who do not read tool names. */
const PLAIN: [RegExp, string][] = [
  [/^intel\.changed_symbols/, 'Found what this commit changed'],
  [/^intel\.entry_points/, 'Listed every way in from outside'],
  [/^intel\.call_graph/, 'Followed the code path'],
  [/^intel\.convention/, 'Compared it with similar code'],
  [/^intel\.(path|taint)/, 'Traced where user input goes'],
  [/^intel\.(symbol|data_classes)/, 'Looked for sensitive data'],
  [/^sandbox\.start/, 'Started a private copy of the app'],
  [/^sandbox\.run_tests/, 'Ran the tests'],
  [/^fixture\.identities/, 'Created test users'],
  [/^http\.request/, 'Sent a test request'],
  [/^worktree\.create/, 'Opened a scratch copy of the code'],
  [/^fs\.edit/, 'Edited the code'],
  [/^tests\.generate/, 'Wrote new tests'],
  [/^policy\.suggest_rule/, 'Suggested a guard rule'],
  [/^rl\.recommend/, 'Asked the defense policy'],
  [/^review\.findings/, "Read the reviewer's notes"],
  [/^git\.push/, 'Tried to push code'],
  [/^git\.blame/, 'Checked the history of this code'],
  [/^deps\./, 'Checked the dependencies'],
  [/^score\.cvss/, 'Scored how severe it is'],
  [/^record\.hypothesis/, 'Wrote down what might be wrong'],
  [/^record\.attack_path/, 'Wrote down how far an attacker could get'],
  [/^record\.(patch_candidate|remediation_plan)/, 'Saved the proposed fix'],
  [/^record\.(check|verification)/, 'Saved the result'],
];
export function plainStep(step: ToolStep): string {
  return PLAIN.find(([re]) => re.test(step.tool))?.[1] ?? step.tool;
}

const KIND_HINTS: [RegExp, DemoComponent['kind'][]][] = [
  [/refund|queue|worker|job/i, ['worker']],
  [/ledger|\bdb\b|sql|query|postgres|store\.|database|lockfile|migration/i, ['data']],
  [/audit|\blog/i, ['logging']],
  [/session|token|auth|login|sso|identit|cus_a|cus_b/i, ['identity']],
  [/cdn|edge|gateway|ingress|rate.?limit|waf/i, ['edge']],
];

function byKind(repo: DemoRepo, kinds: string[]): string | undefined {
  return repo.components.find(c => kinds.includes(c.kind))?.id;
}

/** The main application component (the one a commit to this repository lives in). */
export function coreComponent(repo: DemoRepo): string {
  return byKind(repo, ['service']) ?? byKind(repo, ['site']) ?? repo.components[0]!.id;
}

/** Which component a step touched. Unknown → the core component. */
export function stepComponent(step: ToolStep, repo: DemoRepo, previous?: string): string {
  const core = coreComponent(repo);
  if (step.outcome === 'denied' && /https?:\/\//.test(step.input)) return byKind(repo, ['edge']) ?? core;
  if (/^fixture\.identities/.test(step.tool)) return byKind(repo, ['identity']) ?? core;
  // A request inside the sandbox hits the changed service's endpoint, whoever it is sent as.
  if (/^http\.request/.test(step.tool)) return core;
  if (/^(policy\.suggest_rule|rl\.recommend)/.test(step.tool)) return byKind(repo, ['edge']) ?? core;
  if (/^(record|review)\./.test(step.tool)) return previous ?? core;
  if (/^(sandbox|worktree|fs|tests|git)\./.test(step.tool)) return core;
  const text = `${step.input} ${step.result}`;
  for (const [re, kinds] of KIND_HINTS) {
    const hit = byKind(repo, kinds);
    if (hit && re.test(text)) return hit;
  }
  return core;
}

/** The red team looks for problems and may touch any part of the change. */
const RED_TEAM: ReadonlySet<AgentId> = new Set(['scout', 'probe']);
export const isRedTeam = (agent: AgentId) => RED_TEAM.has(agent);

/**
 * Where the confirmed finding lives, or null when the red team confirmed nothing. Findings in
 * this demo are on the changed service. Only a finding Probe confirmed counts.
 */
export function issueComponent(analysis: Analysis, repo: DemoRepo): string | null {
  const probe = analysis.agents.find(a => a.agent === 'probe');
  return analysis.findings.length > 0 && probe?.status === 'done' ? coreComponent(repo) : null;
}

/**
 * Every step of the run, in orchestrator order, pinned to a component. Red-team steps go where
 * they looked; Trace, the blue team and Verify only ever work on the confirmed issue.
 */
export function ticks(analysis: Analysis, repo: DemoRepo): Tick[] {
  const issue = issueComponent(analysis, repo) ?? coreComponent(repo);
  const out: Tick[] = [];
  for (const agent of analysis.agents) {
    let previous: string | undefined;
    agent.steps.forEach((step, index) => {
      const component = isRedTeam(agent.agent) ? stepComponent(step, repo, previous) : issue;
      previous = component;
      out.push({ agent: agent.agent, team: agent.team, step, index, component });
    });
  }
  return out;
}

/** Components the run touched at all: everything else is "not in this change". */
export function affected(all: Tick[], repo: DemoRepo): Set<string> {
  return new Set([coreComponent(repo), ...all.map(t => t.component)]);
}

/** Ticks played when the red team has finished (Probe's verdict is in). */
export function redTeamEnd(all: Tick[]): number {
  let end = 0;
  all.forEach((t, i) => { if (isRedTeam(t.agent)) end = i + 1; });
  return end;
}

/**
 * State of each component after `played` ticks (`active` is the step in progress, if any).
 * While the red team works, parts it has looked at wait for Probe's verdict ("scanned"). Once
 * Probe is done, the confirmed part turns to "issue" and stays red while Trace and the blue team
 * work on it; it becomes "fixed" only when Verify accepted the fix. Every other part it looked
 * at is "clear".
 */
export function componentStates(all: Tick[], played: number, repo: DemoRepo, analysis: Analysis, accepted: boolean, active?: Tick): Record<string, ComponentState> {
  const touched = affected(all, repo);
  const seen = new Set(all.slice(0, played).map(t => t.component));
  const verdictIn = played >= redTeamEnd(all);
  const issue = verdictIn ? issueComponent(analysis, repo) : null;
  const verifyDone = played >= all.length && all.length > 0;
  const states: Record<string, ComponentState> = {};
  for (const c of repo.components) {
    if (!touched.has(c.id)) states[c.id] = 'outside';
    else if (c.id === issue) states[c.id] = verifyDone && accepted ? 'fixed' : 'issue';
    else if (active?.component === c.id) states[c.id] = 'checking';
    else if (!seen.has(c.id)) states[c.id] = 'waiting';
    else states[c.id] = verdictIn ? 'clear' : 'scanned';
  }
  return states;
}

export const STATE_LABEL: Record<ComponentState, string> = {
  outside: 'Not touched by this change',
  waiting: 'Queued',
  checking: 'Being tested',
  scanned: 'Tested · waiting for proof',
  clear: 'No issue',
  issue: 'Issue confirmed',
  fixed: 'Fixed & verified',
};

export interface Phase { label: string; agents: AgentId[] }
export const PHASES: Phase[] = [
  { label: 'Red team', agents: ['scout', 'probe'] },
  { label: 'Trace', agents: ['trace'] },
  { label: 'Blue team', agents: ['diagnose', 'patch', 'fortify'] },
  { label: 'Verify', agents: ['verify'] },
];
