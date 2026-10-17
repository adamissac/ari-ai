import type { AssessmentState } from '@hackatl/frontend-transport';
import { STATE_RAIL, railSteps } from '@/lib/status';

export type JourneyStatus =
  | 'not_started'
  | 'running'
  | 'completed'
  | 'needs_attention'
  | 'blocked'
  | 'failed'
  | 'not_applicable'
  | 'skipped';

export interface JourneyStage {
  id: 'understand' | 'review' | 'security' | 'repair' | 'verify' | 'monitor';
  label: string;
  status: JourneyStatus;
  detail: string;
}

export const JOURNEY_STATUS: Record<JourneyStatus, string> = {
  not_started: 'Not started',
  running: 'Running',
  completed: 'Completed',
  needs_attention: 'Needs attention',
  blocked: 'Blocked',
  failed: 'Failed',
  not_applicable: 'Not applicable',
  skipped: 'Skipped',
};

const PIPELINE: readonly { id: JourneyStage['id']; label: string; states: readonly AssessmentState[] }[] = [
  { id: 'understand', label: 'Understand', states: ['INDEXING'] },
  { id: 'review', label: 'Review', states: ['FUNCTIONAL_REVIEW'] },
  { id: 'security', label: 'Security test', states: ['RECON', 'VALIDATION', 'ANALYSIS', 'DIAGNOSIS'] },
  { id: 'repair', label: 'Repair', states: ['AWAITING_APPROVAL', 'REMEDIATION'] },
];

const RAIL = new Set<string>(STATE_RAIL);

export interface JourneyInput {
  repoCount: number;
  activeScopeCount: number;
  /** Latest assessment state. Null when the project has no assessment. */
  current: AssessmentState | null;
  /**
   * States the event log shows the run entered for real.
   * Null when that log failed to load — phases stay unmarked rather than skipped.
   */
  visited: readonly AssessmentState[] | null;
  findingStatuses: readonly string[];
  monitoringEnabled: boolean;
  monitoringKnown: boolean;
  monitoringEventCount: number;
  monitoringTruncated: boolean;
  monitoringFailed: boolean;
  newestMonitoringSimulated: boolean;
}

/** Phases of the latest check. A phase is completed only when the log shows it was entered. */
export function projectJourney(input: JourneyInput): JourneyStage[] {
  const stages = PIPELINE.map(group => pipelineStage(group, input));
  stages.push(verifyStage(stages.find(stage => stage.id === 'repair')!, input));
  stages.push(monitorStage(input));
  return stages;
}

/** Real entries only. A transition whose message says it was skipped does not count as entered. */
export function statesFromLog(
  events: readonly { type: string; state: string | null; message: string }[],
): AssessmentState[] {
  const real = new Set<AssessmentState>();
  for (const event of events) {
    if (event.type !== 'assessment.state_changed' || !event.state || !RAIL.has(event.state)) continue;
    const state = event.state as AssessmentState;
    if (event.message.trim().toLowerCase().startsWith('skipped') && !real.has(state)) continue;
    real.add(state);
  }
  return [...real];
}

export function latestAssessmentEvent(
  events: readonly { seq: number; message: string; at: string }[],
): { message: string; at: string } | null {
  const usable = events.filter(event => event.message.trim());
  if (usable.length === 0) return null;
  const latest = usable.reduce((best, event) => (event.seq > best.seq ? event : best));
  return { message: latest.message.trim(), at: latest.at };
}

function pipelineStage(
  group: (typeof PIPELINE)[number],
  input: JourneyInput,
): JourneyStage {
  if (input.current === null && input.repoCount === 0 && group.id === 'understand') {
    return stage(group, 'blocked', 'Connect a repository before a check can run.');
  }
  if (input.current === null && input.repoCount > 0 && input.activeScopeCount === 0 && group.id === 'security') {
    return stage(group, 'blocked', 'Security checks stay blocked until a scope is approved.');
  }
  if (input.current === null) return stage(group, 'not_started', 'No check has been recorded.');
  if (input.visited === null) {
    return stage(group, 'not_started', 'This phase is unmarked because the event log did not load.');
  }

  const visited = new Set(input.visited);
  const steps = railSteps(input.current, visited);
  const phases = group.states.map(state => steps.find(step => step.state === state)!.phase);
  const fault = faultGroup(input.current, visited);
  const someSkipped = phases.includes('skipped');

  if (phases.includes('current')) {
    if (input.current === 'AWAITING_APPROVAL') {
      return stage(group, 'needs_attention', 'A person still has to approve a candidate fix. Nothing is merged or deployed.');
    }
    return stage(group, 'running', 'This is the current phase of the latest check.');
  }
  if (fault === group.id || (fault === 'before' && group.id === 'understand')) {
    return stage(group, terminalStatus(input.current), terminalDetail(input.current, fault === 'before'));
  }
  if (phases.includes('done')) {
    return stage(
      group,
      'completed',
      someSkipped
        ? 'The run entered this phase. A later step inside it is not in the event log.'
        : 'The event log shows the run entered this phase.',
    );
  }
  if (someSkipped) return stage(group, 'skipped', 'The event log does not show the run entering this phase.');
  return stage(group, 'not_started', 'No check has recorded this phase.');
}

function verifyStage(repair: JourneyStage, input: JourneyInput): JourneyStage {
  const accepted = input.findingStatuses.some(status => status === 'verified' || status === 'hardened');
  const rejected = input.findingStatuses.some(status => status === 'patch_rejected' || status === 'needs_recheck');
  if (accepted) {
    return {
      id: 'verify',
      label: 'Verify',
      status: 'completed',
      detail: 'Independent verification accepted a fix in this finding list. That is not a claim about the whole application.',
    };
  }
  if (rejected) {
    return {
      id: 'verify',
      label: 'Verify',
      status: 'needs_attention',
      detail: 'A candidate fix was not accepted. This finding list has no verified fix.',
    };
  }
  if (input.current === null) {
    return { id: 'verify', label: 'Verify', status: 'not_started', detail: 'No check has been recorded.' };
  }
  if (input.visited === null) {
    return { id: 'verify', label: 'Verify', status: 'not_started', detail: 'This phase is unmarked because the event log did not load.' };
  }
  if (repair.status === 'skipped') {
    return { id: 'verify', label: 'Verify', status: 'skipped', detail: 'Repair did not run, so there is no fix to verify.' };
  }
  if (input.current === 'REMEDIATION') {
    return {
      id: 'verify',
      label: 'Verify',
      status: 'running',
      detail: 'A candidate fix is being re-tested. No verdict is in this finding list yet.',
    };
  }
  if (repair.status === 'completed') {
    return {
      id: 'verify',
      label: 'Verify',
      status: 'not_started',
      detail: 'Repair was recorded. This finding list has no verification verdict.',
    };
  }
  return { id: 'verify', label: 'Verify', status: 'not_started', detail: 'No verification verdict is in this finding list.' };
}

function monitorStage(input: JourneyInput): JourneyStage {
  if (!input.monitoringKnown) {
    return { id: 'monitor', label: 'Monitor', status: 'not_started', detail: 'Monitoring events have not loaded.' };
  }
  if (!input.monitoringEnabled) {
    return { id: 'monitor', label: 'Monitor', status: 'not_applicable', detail: 'Monitoring is off for this project.' };
  }
  if (input.monitoringFailed) {
    return { id: 'monitor', label: 'Monitor', status: 'failed', detail: 'A recorded monitoring event failed.' };
  }
  if (input.monitoringEventCount > 0) {
    const count = input.monitoringTruncated
      ? `The newest page has ${input.monitoringEventCount} events.`
      : `${input.monitoringEventCount} monitoring event${input.monitoringEventCount === 1 ? '' : 's'} recorded.`;
    const simulated = input.newestMonitoringSimulated ? ' The newest event is labelled simulated.' : '';
    return { id: 'monitor', label: 'Monitor', status: 'running', detail: `Monitoring is on. ${count}${simulated}` };
  }
  return { id: 'monitor', label: 'Monitor', status: 'not_started', detail: 'Monitoring is on. No events are recorded yet.' };
}

function faultGroup(
  current: AssessmentState,
  visited: ReadonlySet<AssessmentState>,
): JourneyStage['id'] | 'before' | null {
  if (current !== 'FAILED' && current !== 'CANCELLED' && current !== 'BUDGET_EXHAUSTED') return null;
  const furthest = [...STATE_RAIL].reverse().find(state => visited.has(state));
  if (!furthest) return 'before';
  return PIPELINE.find(group => group.states.includes(furthest))?.id ?? 'before';
}

function terminalStatus(current: AssessmentState): JourneyStatus {
  return current === 'FAILED' ? 'failed' : 'needs_attention';
}

function terminalDetail(current: AssessmentState, beforeUnderstanding: boolean): string {
  if (beforeUnderstanding && current === 'FAILED') return 'The check failed before code understanding was recorded.';
  if (beforeUnderstanding && current === 'CANCELLED') return 'The check was cancelled before code understanding was recorded.';
  if (beforeUnderstanding) return 'The check ran out of budget before code understanding was recorded.';
  if (current === 'FAILED') return 'The latest check failed during this phase.';
  if (current === 'CANCELLED') return 'The latest check was cancelled during this phase.';
  return 'The latest check ran out of budget during this phase.';
}

function stage(
  group: { id: JourneyStage['id']; label: string },
  status: JourneyStatus,
  detail: string,
): JourneyStage {
  return { id: group.id, label: group.label, status, detail };
}
