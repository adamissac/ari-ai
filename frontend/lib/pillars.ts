/**
 * The product loop as five connected steps, each carrying this project's recorded
 * counts. Words are explanation; numbers come only from loaded records, and a count
 * that did not load is `null` (shown as "not loaded"), never zero.
 */
export type LoopTone = 'empty' | 'active' | 'attention' | 'good' | 'unknown';

export interface LoopNode {
  id: 'understand' | 'review' | 'attack' | 'prove' | 'monitor';
  pillar: 'Shared intelligence' | 'Pillar 1' | 'Pillar 2' | 'Pillar 3';
  title: string;
  question: string;
  status: string;
  tone: LoopTone;
  href: string;
}

export interface LoopInput {
  projectId: string;
  repoCount: number;
  activeScopeCount: number;
  assessmentCount: number | null;
  findings: readonly { kind: string; status: string }[] | null;
  monitoringEnabled: boolean;
  monitoringEventCount: number | null;
  reassessmentCount: number | null;
}

const UNTESTED = new Set(['hypothesis']);
const DISMISSED = new Set(['refuted', 'closed', 'accepted_risk', 'inconclusive']);
const FIXED = new Set(['verified', 'hardened']);

const plural = (n: number, one: string, many = `${one}s`): string => `${n} ${n === 1 ? one : many}`;

export function pillarLoop(input: LoopInput): LoopNode[] {
  const base = `/projects/${input.projectId}`;
  const f = input.findings;
  const functional = f?.filter(x => x.kind === 'functional' && !DISMISSED.has(x.status) && !FIXED.has(x.status)).length ?? null;
  const confirmed = f?.filter(x => x.kind === 'security' && !UNTESTED.has(x.status) && !DISMISSED.has(x.status) && !FIXED.has(x.status)).length ?? null;
  const suspicions = f?.filter(x => x.kind === 'security' && UNTESTED.has(x.status)).length ?? null;
  const fixed = f?.filter(x => FIXED.has(x.status)).length ?? null;
  const checked = input.assessmentCount !== null && input.assessmentCount > 0;

  const understand: LoopNode = {
    id: 'understand', pillar: 'Shared intelligence', title: 'Understand the code',
    question: 'What is this software supposed to do?',
    status: input.repoCount === 0 ? 'No repository connected yet.' : `${plural(input.repoCount, 'repository', 'repositories')} connected${input.assessmentCount === null ? '.' : `, ${plural(input.assessmentCount, 'check')} run.`}`,
    tone: input.repoCount === 0 ? 'empty' : 'good', href: `${base}#connect-repo`,
  };
  const review: LoopNode = {
    id: 'review', pillar: 'Pillar 1', title: 'Review the change',
    question: 'Does the change do what it was meant to?',
    status: functional === null ? 'Findings did not load.' : !checked ? 'Not checked yet.' : functional === 0 ? 'No open problems in how the code behaves.' : `${plural(functional, 'behaviour problem')} still open.`,
    tone: functional === null ? 'unknown' : !checked ? 'empty' : functional === 0 ? 'good' : 'attention', href: `${base}/findings`,
  };
  const attack: LoopNode = {
    id: 'attack', pillar: 'Pillar 2', title: 'Test it like an attacker',
    question: 'Could someone break in or misuse it?',
    status: input.activeScopeCount === 0 ? 'Blocked until a person approves a safe test environment.'
      : confirmed === null || suspicions === null ? 'Findings did not load.'
      : !checked ? 'Not tested yet.'
      : confirmed === 0 && suspicions === 0 ? 'No open security problems in this list.'
      : [confirmed > 0 ? `${plural(confirmed, 'confirmed weakness', 'confirmed weaknesses')}` : null, suspicions > 0 ? `${plural(suspicions, 'untested suspicion')}` : null].filter(Boolean).join(', ') + '.',
    tone: input.activeScopeCount === 0 ? 'attention' : confirmed === null ? 'unknown' : !checked ? 'empty' : confirmed > 0 ? 'attention' : suspicions && suspicions > 0 ? 'active' : 'good',
    href: input.activeScopeCount === 0 ? `${base}/scopes` : `${base}/findings`,
  };
  const prove: LoopNode = {
    id: 'prove', pillar: 'Pillar 2', title: 'Fix it and prove it',
    question: 'Is there a fix that independent tests accept?',
    status: fixed === null ? 'Findings did not load.' : fixed === 0 ? 'No independently verified fix yet.' : `${plural(fixed, 'fix', 'fixes')} accepted by independent tests. Proposed only; nothing was merged or deployed.`,
    tone: fixed === null ? 'unknown' : fixed === 0 ? 'empty' : 'good', href: `${base}/findings`,
  };
  const monitor: LoopNode = {
    id: 'monitor', pillar: 'Pillar 3', title: 'Keep watching',
    question: 'What happens when the code changes again?',
    status: !input.monitoringEnabled ? 'Monitoring is off for this project.'
      : input.monitoringEventCount === null ? 'Monitoring events did not load.'
      : input.monitoringEventCount === 0 ? 'On. No code change has arrived yet.'
      : `On. ${plural(input.monitoringEventCount, 'change event')} received${input.reassessmentCount ? `, ${plural(input.reassessmentCount, 're-check')} requested` : ''}.`,
    tone: !input.monitoringEnabled ? 'empty' : input.monitoringEventCount === null ? 'unknown' : input.monitoringEventCount === 0 ? 'empty' : 'active',
    href: `${base}/monitoring`,
  };
  return [understand, review, attack, prove, monitor];
}
