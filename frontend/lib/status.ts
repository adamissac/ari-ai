import type {
  AgentName, AgentRunStatus, ApprovalStatus, AssessmentState, EventStatus, ExpectationStatus,
  FindingStatus, ScopeStatus, SeverityLevel, SnapshotStatus, ValidationOutcome, VerificationVerdict,
} from '@hackatl/frontend-transport';

/** Every status renders as text + glyph + tone; colour is never the only signal. */
export type Tone = 'ok' | 'warn' | 'bad' | 'info' | 'neutral' | 'accent';
export interface StatusView { label: string; tone: Tone; glyph: string }

const v = (label: string, tone: Tone, glyph: string): StatusView => ({ label, tone, glyph });

export const FINDING_STATUS: Record<FindingStatus, StatusView> = {
  hypothesis: v('Hypothesis', 'info', '?'),
  validated: v('Validated', 'warn', '!'),
  refuted: v('Refuted', 'neutral', '×'),
  inconclusive: v('Inconclusive', 'neutral', '~'),
  diagnosed: v('Diagnosed', 'warn', '!'),
  patch_proposed: v('Patch proposed', 'accent', '±'),
  verified: v('Verified fix', 'ok', '✓'),
  patch_rejected: v('Patch rejected', 'bad', '×'),
  unresolved: v('Unresolved', 'bad', '!'),
  hardened: v('Hardened', 'ok', '✓'),
  accepted_risk: v('Accepted risk', 'neutral', '◇'),
  closed: v('Closed', 'neutral', '—'),
  needs_recheck: v('Stale — needs recheck', 'warn', '↻'),
};

export const ASSESSMENT_STATE: Record<AssessmentState, StatusView> = {
  CREATED: v('Created', 'neutral', '○'),
  SCOPE_CHECK: v('Scope check', 'info', '◔'),
  INDEXING: v('Indexing', 'info', '◔'),
  FUNCTIONAL_REVIEW: v('Functional review', 'info', '◔'),
  RECON: v('Recon', 'info', '◔'),
  VALIDATION: v('Validation', 'info', '◔'),
  ANALYSIS: v('Analysis', 'info', '◔'),
  DIAGNOSIS: v('Diagnosis', 'info', '◔'),
  AWAITING_APPROVAL: v('Awaiting human approval', 'warn', '⏸'),
  REMEDIATION: v('Remediation', 'info', '◔'),
  HARDENING: v('Hardening', 'info', '◔'),
  REPORTING: v('Reporting', 'info', '◔'),
  COMPLETED: v('Completed', 'ok', '✓'),
  FAILED: v('Failed', 'bad', '×'),
  CANCELLED: v('Cancelled', 'neutral', '■'),
  BUDGET_EXHAUSTED: v('Budget exhausted', 'bad', '$'),
};

export const AGENT_RUN_STATUS: Record<AgentRunStatus, StatusView> = {
  queued: v('Queued', 'neutral', '○'),
  running: v('Running', 'info', '◔'),
  succeeded: v('Succeeded', 'ok', '✓'),
  failed: v('Failed', 'bad', '×'),
  cancelled: v('Cancelled', 'neutral', '■'),
};

export const VALIDATION_OUTCOME: Record<ValidationOutcome, StatusView> = {
  confirmed: v('Confirmed by Probe', 'warn', '!'),
  refuted: v('Ruled out by Probe', 'ok', '×'),
  inconclusive: v('Inconclusive', 'neutral', '~'),
};

export const VERDICT: Record<VerificationVerdict, StatusView> = {
  accepted: v('Verify: accepted', 'ok', '✓'),
  rejected: v('Verify: rejected', 'bad', '×'),
};

export const SCOPE_STATUS: Record<ScopeStatus, StatusView> = {
  pending: v('Pending approval', 'warn', '⏸'),
  active: v('Active', 'ok', '✓'),
  expired: v('Expired', 'neutral', '—'),
  revoked: v('Revoked', 'bad', '×'),
};

export const APPROVAL_STATUS: Record<ApprovalStatus, StatusView> = {
  pending: v('Pending', 'warn', '⏸'),
  approved: v('Approved', 'ok', '✓'),
  declined: v('Declined', 'bad', '×'),
};

export const SNAPSHOT_STATUS: Record<SnapshotStatus, StatusView> = {
  pending: v('Pending', 'neutral', '○'),
  indexing: v('Indexing', 'info', '◔'),
  ready: v('Indexed', 'ok', '✓'),
  failed: v('Index failed', 'bad', '×'),
};

export const EVENT_STATUS: Record<EventStatus, StatusView> = {
  received: v('Received', 'neutral', '○'),
  processing: v('Processing', 'info', '◔'),
  processed: v('Processed', 'ok', '✓'),
  ignored: v('Ignored', 'neutral', '—'),
  failed: v('Failed', 'bad', '×'),
};

export const EXPECTATION_STATUS: Record<ExpectationStatus, StatusView> = {
  confirmed: v('Confirmed', 'ok', '✓'),
  inferred: v('Inferred', 'info', '?'),
  ambiguous: v('Ambiguous', 'warn', '~'),
  conflicting: v('Conflicting', 'bad', '!'),
  rejected: v('Rejected', 'neutral', '×'),
};

export const SEVERITY: Record<SeverityLevel, StatusView> = {
  info: v('Info', 'neutral', '·'),
  low: v('Low', 'info', '▂'),
  medium: v('Medium', 'warn', '▄'),
  high: v('High', 'bad', '▆'),
  critical: v('Critical', 'bad', '█'),
};

export const TERMINAL_STATES: ReadonlySet<AssessmentState> = new Set(['COMPLETED', 'FAILED', 'CANCELLED', 'BUDGET_EXHAUSTED']);

/** Orchestrator happy path (docs/08). Terminal failure states are shown separately. */
export const STATE_RAIL: readonly AssessmentState[] = [
  'CREATED', 'SCOPE_CHECK', 'INDEXING', 'FUNCTIONAL_REVIEW', 'RECON', 'VALIDATION', 'ANALYSIS',
  'DIAGNOSIS', 'AWAITING_APPROVAL', 'REMEDIATION', 'HARDENING', 'REPORTING', 'COMPLETED',
];

export type RailStep = { state: AssessmentState; phase: 'done' | 'current' | 'upcoming' | 'skipped' };

/**
 * Rail positions come from the states the run actually entered (from the
 * persisted event log), not from assumptions: a state that was jumped over is
 * "skipped", never painted as done.
 */
export function railSteps(current: AssessmentState, visited: ReadonlySet<AssessmentState>): RailStep[] {
  const idx = STATE_RAIL.indexOf(current);
  const furthest = idx >= 0 ? idx : Math.max(-1, ...STATE_RAIL.map((s, i) => (visited.has(s) ? i : -1)));
  return STATE_RAIL.map((state, i) => {
    if (state === current && !TERMINAL_STATES.has(current)) return { state, phase: 'current' };
    if (state === current && current === 'COMPLETED') return { state, phase: 'done' };
    if (i <= furthest) return { state, phase: visited.has(state) ? 'done' : 'skipped' };
    return { state, phase: 'upcoming' };
  });
}

export interface AgentRole {
  name: AgentName;
  label: string;
  team: 'Functional' | 'Red' | 'Blue' | 'Independent';
  role: string;
  /** One line a newcomer can read. Not a claim that this run succeeded. */
  job: string;
  /** What a completed run of this agent is supposed to pass on. */
  handsTo: string;
}

/** The eight product runtime agents, in the order the orchestrator runs them. */
export const AGENTS: readonly AgentRole[] = [
  { name: 'reviewer', label: 'Reviewer', team: 'Functional', role: 'Intent-aware functional review and repair', job: 'Checks whether the change does what was intended.', handsTo: 'Functional findings and the intended behaviour, for the security team.' },
  { name: 'scout', label: 'Scout', team: 'Red', role: 'Evidence-backed vulnerability hypotheses', job: 'Maps where the code could be vulnerable.', handsTo: 'Hypotheses for Probe to test. Not yet confirmed weaknesses.' },
  { name: 'probe', label: 'Probe', team: 'Red', role: 'Non-destructive validation in the authorized sandbox', job: 'Proves or disproves those hypotheses in an approved sandbox.', handsTo: 'Confirmed, refuted, or inconclusive check results.' },
  { name: 'trace', label: 'Trace', team: 'Red', role: 'Attack path and impact', job: 'Follows what a confirmed weakness could affect.', handsTo: 'An attack path, with unverified steps still labelled as hypotheses.' },
  { name: 'diagnose', label: 'Diagnose', team: 'Blue', role: 'Root cause and remediation plan', job: 'Finds the cause and what would need to change.', handsTo: 'A remediation plan. Patch does not start until a person approves.' },
  { name: 'patch', label: 'Patch', team: 'Blue', role: 'Candidate fix in an isolated worktree', job: 'Proposes a fix without changing production.', handsTo: 'A candidate diff for independent verification. Nothing is merged.' },
  { name: 'verify', label: 'Verify', team: 'Independent', role: 'Re-runs exploit and functional tests', job: 'Accepts or rejects the fix on executed tests.', handsTo: 'A pass or fail. A rejected patch is not a fix.' },
  { name: 'fortify', label: 'Fortify', team: 'Blue', role: 'Hardening and regression tests', job: 'Suggests how to keep this kind of issue from coming back.', handsTo: 'Hardening notes and, when recorded, a regression test.' },
];

export function agentRole(name: AgentName): AgentRole {
  return AGENTS.find(a => a.name === name) ?? { name, label: name, team: 'Independent', role: '', job: '', handsTo: '' };
}

export interface RunFacts {
  status: string;
  tool_calls: readonly unknown[];
  error?: { code: string; message: string } | null;
}

/** Summary uses only persisted runs. An agent with no run stays empty. */
export function agentRunSummary(runs: readonly RunFacts[]): string {
  if (runs.length === 0) return 'Has not run.';
  const latest = runs[runs.length - 1];
  const tools = runs.reduce((n, run) => n + run.tool_calls.length, 0);
  const runsLabel = `${runs.length} recorded run${runs.length === 1 ? '' : 's'}, ${tools} tool call${tools === 1 ? '' : 's'}.`;
  if (latest?.status === 'failed' && latest.error) return `${latest.error.code}: ${latest.error.message}. ${runsLabel}`;
  if (latest?.status === 'running' || latest?.status === 'queued') return `${latest.status === 'running' ? 'Running now.' : 'Queued.'} ${runsLabel}`;
  return runsLabel;
}

/** What is still open between this agent and the next, from the runs that exist. */
export function handoffNote(own: readonly RunFacts[], next: readonly RunFacts[] | null): string {
  if (own.length === 0) return 'Nothing to hand off: this agent has not run.';
  const latest = own[own.length - 1];
  if (latest?.status === 'failed') return 'This run failed, so there is no successful handoff.';
  if (latest?.status === 'running' || latest?.status === 'queued') return 'Still working. The next agent has not received a finished result.';
  if (next === null) return 'This is the last agent in the sequence.';
  if (next.length === 0) return 'Finished. The next agent has not run yet.';
  return 'Finished, and the next agent has a recorded run.';
}

/** provider_mode is persisted per run; 'live' is the only value that means a real model call. */
export function providerLabel(mode: string): StatusView {
  if (mode === 'live') return v('Live provider', 'ok', '●');
  if (mode === 'replay') return v('Replay of recorded run', 'warn', '↺');
  if (mode === 'fake') return v('Test provider (scripted)', 'warn', '⚙');
  if (mode === 'none') return v('Deterministic (no model call)', 'neutral', '=');
  return v(`Provider: ${mode}`, 'neutral', '?');
}
