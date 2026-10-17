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

export interface AgentRole { name: AgentName; label: string; team: 'Functional' | 'Red' | 'Blue' | 'Independent'; role: string }

/** The eight product runtime agents, in orchestrated order. */
export const AGENTS: readonly AgentRole[] = [
  { name: 'reviewer', label: 'Reviewer', team: 'Functional', role: 'Intent-aware functional review and repair' },
  { name: 'scout', label: 'Scout', team: 'Red', role: 'Evidence-backed vulnerability hypotheses' },
  { name: 'probe', label: 'Probe', team: 'Red', role: 'Non-destructive validation in the authorized sandbox' },
  { name: 'trace', label: 'Trace', team: 'Red', role: 'Attack path and impact' },
  { name: 'diagnose', label: 'Diagnose', team: 'Blue', role: 'Root cause and remediation plan' },
  { name: 'patch', label: 'Patch', team: 'Blue', role: 'Candidate fix in an isolated worktree' },
  { name: 'verify', label: 'Verify', team: 'Independent', role: 'Re-runs exploit and functional tests' },
  { name: 'fortify', label: 'Fortify', team: 'Blue', role: 'Hardening and regression tests' },
];

export function agentRole(name: AgentName): AgentRole {
  return AGENTS.find(a => a.name === name) ?? { name, label: name, team: 'Independent', role: '' };
}

/** provider_mode is persisted per run; 'live' is the only value that means a real model call. */
export function providerLabel(mode: string): StatusView {
  if (mode === 'live') return v('Live provider', 'ok', '●');
  if (mode === 'replay') return v('Replay of recorded run', 'warn', '↺');
  if (mode === 'fake') return v('Test provider (scripted)', 'warn', '⚙');
  if (mode === 'deterministic') return v('No model call (deterministic checks)', 'neutral', '⚖');
  return v(`Provider: ${mode}`, 'neutral', '?');
}
