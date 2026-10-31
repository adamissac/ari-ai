import type { AssessmentState } from '@hackatl/frontend-transport';
import type { RelayItem } from '@/lib/relay';

/**
 * What one finished assessment did, in the order a customer reads it: found → fix
 * proposed → approved → verified. Every number comes from the persisted findings,
 * agent runs and approval records passed in; nothing is inferred beyond them.
 */
interface FindingFacts { id: string; kind: string; status: string }
interface RunFacts { agent: string; step_key: string; status: string; provider_mode: string }
interface ApprovalFacts { subject_type: string; status: string }

const CONFIRMED: ReadonlySet<string> = new Set(['validated', 'diagnosed', 'patch_proposed', 'verified', 'patch_rejected', 'unresolved', 'hardened']);
const VERIFIED: ReadonlySet<string> = new Set(['verified', 'hardened']);
const SECURITY_AGENTS: ReadonlySet<string> = new Set(['scout', 'probe']);

export interface OutcomeCounts {
  findings: number;
  confirmed: number;
  ruledOut: number;
  unconfirmed: number;
  fixesProposed: number;
  fixesVerified: number;
  approved: number;
  declined: number;
  pending: number;
}

export function outcomeCounts(findings: readonly FindingFacts[], runs: readonly RunFacts[], approvals: readonly ApprovalFacts[] | null): OutcomeCounts {
  const confirmed = findings.filter(f => CONFIRMED.has(f.status)).length;
  const ruledOut = findings.filter(f => f.status === 'refuted').length;
  // A proposed fix is a Patch run that finished for that finding (step key `patch:<finding id>`).
  const patched = new Set(runs.filter(r => r.agent === 'patch' && r.status === 'succeeded' && r.step_key.startsWith('patch:')).map(r => r.step_key.slice('patch:'.length)));
  const fixApprovals = (approvals ?? []).filter(a => a.subject_type === 'remediation');
  return {
    findings: findings.length,
    confirmed,
    ruledOut,
    unconfirmed: findings.length - confirmed - ruledOut,
    fixesProposed: findings.filter(f => patched.has(f.id)).length,
    fixesVerified: findings.filter(f => VERIFIED.has(f.status)).length,
    approved: fixApprovals.filter(a => a.status === 'approved').length,
    declined: fixApprovals.filter(a => a.status === 'declined').length,
    pending: fixApprovals.filter(a => a.status === 'pending').length,
  };
}

export type Coverage =
  | { kind: 'full'; ran: string[] }
  | { kind: 'limited'; ran: string[]; gaps: string[] };

/**
 * For a completed run with no findings: which agents actually finished, and what
 * keeps the result from being read as a clean security verdict.
 */
export function coverage(relay: readonly RelayItem[], runs: readonly RunFacts[], skipNote: string | null): Coverage {
  const agents = relay.flatMap(item => (item.kind === 'agent' ? [item] : []));
  const ran = agents.filter(a => a.status === 'done').map(a => a.label);
  const gaps: string[] = [];
  const failed = agents.filter(a => a.status === 'failed' || a.status === 'cancelled').map(a => a.label);
  if (failed.length) gaps.push(`${failed.join(', ')} stopped with an error, so ${failed.length === 1 ? 'its' : 'their'} part of the check is missing.`);
  if (!agents.some(a => SECURITY_AGENTS.has(a.agent) && a.status === 'done')) {
    gaps.push(skipNote
      ? `The security agents did not test anything: the run ended early (${skipNote}).`
      : 'The security agents did not test anything in this run.');
  }
  if (runs.some(r => r.provider_mode !== 'live' && r.provider_mode !== 'none')) {
    gaps.push('Some model turns were not live (recorded or scripted), so this run demonstrates the workflow rather than a fresh analysis.');
  }
  return gaps.length ? { kind: 'limited', ran, gaps } : { kind: 'full', ran };
}

/** Plain-language cause and next step for an assessment that did not finish. */
export function stoppedExplanation(state: AssessmentState, code: string | null): { cause: string; next: string } {
  if (state === 'CANCELLED') return { cause: 'Someone cancelled this check before it finished.', next: 'Start a new check of the same commit when you are ready.' };
  if (state === 'BUDGET_EXHAUSTED' || code === 'BUDGET_EXHAUSTED') {
    return { cause: 'This check reached its spending or time limit and was stopped, never silently extended.', next: 'Raise the default assessment budget in Settings, then start a new check of the same commit.' };
  }
  switch (code) {
    case 'SCOPE_DENIED':
      return { cause: 'The sandbox testing approval did not cover this repository or had expired.', next: 'Approve sandbox testing again under Authorized scopes, then start a new check.' };
    case 'SANDBOX_START_FAILED':
    case 'SANDBOX_TIMEOUT':
      return { cause: 'The isolated test copy of the repository could not be built or started in time.', next: 'Check the build recipe in Setup (question 1), then start a new check.' };
    case 'LLM_UNAVAILABLE':
    case 'LLM_REFUSAL':
    case 'LLM_OUTPUT_TRUNCATED':
      return { cause: 'The AI model provider did not return a usable answer.', next: 'This is usually temporary. Start a new check of the same commit in a few minutes.' };
    case 'SUBSYSTEM_UNAVAILABLE':
    case 'JOB_LEASE_EXPIRED':
      return { cause: 'A service this check depends on (GitHub, the worker or the sandbox) was unavailable.', next: 'This is usually temporary. Start a new check of the same commit in a few minutes.' };
    case 'KILL_SWITCH':
      return { cause: 'An operator paused all assessments.', next: 'Start a new check once assessments are resumed.' };
    default:
      return { cause: 'The check stopped with an error before it finished.', next: 'Start a new check of the same commit. If it fails again, share the request details below with support.' };
  }
}
