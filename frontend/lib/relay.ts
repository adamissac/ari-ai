import type { AgentName, AssessmentState } from '@hackatl/frontend-transport';
import { agentRole } from '@/lib/status';

/**
 * The eight agents as one relay, in orchestrated order, with the human approval
 * gate where the orchestrator pauses. Status and handoff text come only from the
 * persisted runs and findings passed in.
 */
export type RelayStatus = 'not_run' | 'queued' | 'running' | 'done' | 'failed' | 'cancelled';

export interface RelayTile {
  kind: 'agent';
  agent: AgentName;
  label: string;
  stage: string;
  job: string;
  status: RelayStatus;
  statusText: string;
  handoff: string;
}
export interface RelayGate { kind: 'gate'; status: 'waiting' | 'passed' | 'declined' | 'not_reached' | 'not_used'; text: string }
export type RelayItem = RelayTile | RelayGate;

interface RunFacts { agent: AgentName; status: string; tool_calls: readonly unknown[] }
/** A persisted approval record for this assessment. */
export interface ApprovalFacts { subject_type: string; status: string }
interface FindingFacts { kind: string; status: string }

const ORDER: readonly { agent: AgentName; stage: string; job: string }[] = [
  { agent: 'reviewer', stage: 'Check the change', job: 'Reads the change and checks it does what was intended.' },
  { agent: 'scout', stage: 'Attack safely', job: 'Looks for places an attacker could get in.' },
  { agent: 'probe', stage: 'Attack safely', job: 'Tries each suspicion in a sealed-off test copy.' },
  { agent: 'trace', stage: 'Attack safely', job: 'Works out what a real weakness could reach.' },
  { agent: 'diagnose', stage: 'Plan the fix', job: 'Finds the root cause and plans a fix.' },
  { agent: 'patch', stage: 'Fix', job: 'Writes a proposed fix in an isolated copy.' },
  { agent: 'verify', stage: 'Prove', job: 'Re-runs the attack and the normal tests on the fix.' },
  { agent: 'fortify', stage: 'Prevent', job: 'Suggests how to stop it coming back.' },
];

const STATUS_TEXT: Record<RelayStatus, string> = {
  not_run: 'Has not run',
  queued: 'Waiting to start',
  running: 'Working now',
  done: 'Finished',
  failed: 'Failed',
  cancelled: 'Cancelled',
};

/** Statuses that only exist after a test confirmed the weakness. Closed, accepted-risk, stale and inconclusive are not on this list. */
const CONFIRMED_STATUSES: ReadonlySet<string> = new Set(['validated', 'diagnosed', 'patch_proposed', 'verified', 'patch_rejected', 'unresolved', 'hardened']);

const plural = (n: number, one: string, many = `${one}s`): string => `${n} ${n === 1 ? one : many}`;

function statusOf(runs: readonly RunFacts[]): RelayStatus {
  const latest = runs[runs.length - 1];
  if (!latest) return 'not_run';
  if (latest.status === 'succeeded') return 'done';
  if (latest.status === 'failed' || latest.status === 'cancelled' || latest.status === 'queued' || latest.status === 'running') return latest.status;
  return 'not_run';
}

function handoff(agent: AgentName, status: RelayStatus, findings: readonly FindingFacts[]): string {
  if (status === 'not_run') return 'Nothing handed on yet.';
  if (status === 'failed') return 'Stopped with an error, so nothing was handed on.';
  if (status === 'cancelled') return 'Cancelled before handing anything on.';
  if (status !== 'done') return 'Still working.';
  const sec = findings.filter(f => f.kind === 'security');
  switch (agent) {
    case 'reviewer': {
      const n = findings.filter(f => f.kind === 'functional').length;
      return n === 0 ? 'Recorded no behaviour problems.' : `Recorded ${plural(n, 'behaviour problem')}.`;
    }
    case 'scout':
      return sec.length === 0 ? 'Recorded no security suspicions.' : `Passed ${plural(sec.length, 'suspicion')} to Probe.`;
    case 'probe': {
      const refuted = sec.filter(f => f.status === 'refuted').length;
      const open = sec.filter(f => f.status === 'hypothesis').length;
      const inconclusive = sec.filter(f => f.status === 'inconclusive').length;
      const confirmed = sec.filter(f => CONFIRMED_STATUSES.has(f.status)).length;
      const parts = [
        confirmed ? `${confirmed} confirmed` : null,
        refuted ? `${refuted} ruled out` : null,
        inconclusive ? `${inconclusive} inconclusive` : null,
        open ? `${open} still marked unconfirmed` : null,
      ].filter(Boolean);
      return parts.length ? `Test results: ${parts.join(', ')}. Each finding shows its recorded test.` : 'Finished. Each finding shows its recorded test.';
    }
    case 'verify': {
      const accepted = findings.filter(f => f.status === 'verified' || f.status === 'hardened').length;
      const rejected = findings.filter(f => f.status === 'patch_rejected').length;
      if (accepted === 0 && rejected === 0) return 'Finished. Each finding shows its recorded verdict.';
      return [accepted ? `${plural(accepted, 'fix', 'fixes')} accepted` : null, rejected ? `${rejected} rejected` : null].filter(Boolean).join(', ') + '.';
    }
    default:
      return 'Finished and handed on. Details are on each finding.';
  }
}

export function agentRelay(input: { runs: readonly RunFacts[]; findings: readonly FindingFacts[]; state: AssessmentState; approvals?: readonly ApprovalFacts[] | null }): RelayItem[] {
  const items: RelayItem[] = [];
  for (const step of ORDER) {
    if (step.agent === 'patch') items.push(gate(input));
    const runs = input.runs.filter(r => r.agent === step.agent);
    const status = statusOf(runs);
    items.push({
      kind: 'agent', agent: step.agent, label: agentRole(step.agent).label, stage: step.stage, job: step.job,
      status, statusText: STATUS_TEXT[status], handoff: handoff(step.agent, status, input.findings),
    });
  }
  return items;
}

function gate(input: { runs: readonly RunFacts[]; state: AssessmentState; approvals?: readonly ApprovalFacts[] | null }): RelayGate {
  if (input.state === 'AWAITING_APPROVAL') return { kind: 'gate', status: 'waiting', text: 'Waiting for a person to approve a fix. No code is changed until then.' };
  // The approval record is the only evidence of a decision; a patch run proves nothing about who approved.
  if (!input.approvals) return { kind: 'gate', status: 'not_reached', text: 'The approval record could not be read, so whether a person approved is unknown.' };
  const remediation = input.approvals.filter(a => a.subject_type === 'remediation');
  if (remediation.some(a => a.status === 'approved')) return { kind: 'gate', status: 'passed', text: 'A person approved building a fix.' };
  if (remediation.some(a => a.status === 'declined')) return { kind: 'gate', status: 'declined', text: 'A person declined the fix. No fix was built.' };
  if (remediation.some(a => a.status === 'pending')) return { kind: 'gate', status: 'waiting', text: 'Waiting for a person to approve a fix. No code is changed until then.' };
  const done = input.state === 'COMPLETED' || input.state === 'FAILED' || input.state === 'CANCELLED' || input.state === 'BUDGET_EXHAUSTED';
  if (done) return { kind: 'gate', status: 'not_used', text: 'No approval record: no fix was approved or built.' };
  return { kind: 'gate', status: 'not_reached', text: 'A person must approve before any fix is built.' };
}

/**
 * One sentence on what the non-live model turns were, built per provider mode.
 * Only fake/replay turns are "scripted"; deterministic runs made no model call;
 * live turns are counted as live. Empty when every turn was live.
 */
export function providerNote(counts: Iterable<readonly [string, number]>): string {
  const entries = [...counts];
  if (entries.length === 0 || entries.every(([mode]) => mode === 'live')) return '';
  const part = (mode: string, n: number): string => {
    if (mode === 'live') return `${n} from a live model`;
    if (mode === 'fake') return `${n} scripted`;
    if (mode === 'replay') return `${n} replayed from a recording`;
    if (mode === 'none') return `${n} with no model call`;
    return `${n} from an unrecognised provider mode (${mode})`;
  };
  return `Tool execution, sandbox checks, tests and persistence are still real. Model replies: ${entries.map(([m, n]) => part(m, n)).join(', ')}.`;
}
