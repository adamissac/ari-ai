const RUNNING = new Set([
  'CREATED', 'SCOPE_CHECK', 'INDEXING', 'FUNCTIONAL_REVIEW', 'RECON', 'VALIDATION',
  'ANALYSIS', 'DIAGNOSIS', 'REMEDIATION', 'HARDENING', 'REPORTING',
]);

const CLOSED = new Set(['verified', 'hardened', 'closed', 'refuted', 'accepted_risk']);
const CONFIRMED = new Set(['validated', 'diagnosed', 'patch_proposed', 'unresolved', 'patch_rejected', 'needs_recheck']);

export interface OverviewInput {
  projectId: string;
  repoCount: number;
  activeScopeCount: number;
  monitoringEnabled: boolean;
  assessments: readonly { id: string; state: string; created_at: string }[];
  findings: readonly { status: string; kind: string }[];
}

export interface Overview {
  headline: string;
  detail: string;
  codeOpen: number;
  securityOpen: number;
  verifiedFixes: number;
  monitoring: 'enabled' | 'disabled';
  action: { label: string; href: string };
}

/** One next step and three counts, taken only from records the page already loaded. */
export function projectOverview(input: OverviewInput): Overview {
  const latest = [...input.assessments].sort((a, b) => (a.created_at < b.created_at ? 1 : -1))[0];
  const codeOpen = input.findings.filter(f => f.kind === 'functional' && !CLOSED.has(f.status)).length;
  const securityOpen = input.findings.filter(f => f.kind === 'security' && CONFIRMED.has(f.status)).length;
  const verifiedFixes = input.findings.filter(f => f.status === 'verified' || f.status === 'hardened').length;
  const base = { codeOpen, securityOpen, verifiedFixes, monitoring: input.monitoringEnabled ? 'enabled' as const : 'disabled' as const };

  if (input.repoCount === 0) {
    return {
      ...base,
      headline: 'No repository is connected yet.',
      detail: 'Connect a repository before any check can run.',
      action: { label: 'Connect a repository', href: '#connect-repo' },
    };
  }
  if (input.activeScopeCount === 0) {
    return {
      ...base,
      headline: 'A repository is connected. No safe test environment is approved.',
      detail: 'Security checks stay blocked until a different member approves a scope.',
      action: { label: 'Approve a safe test environment', href: `/projects/${input.projectId}/scopes` },
    };
  }
  if (!latest) {
    return {
      ...base,
      headline: 'Nothing has been checked yet.',
      detail: 'A scope is approved. The next step is to run a review of one commit.',
      action: { label: 'Run a review', href: '#start-assessment' },
    };
  }
  if (RUNNING.has(latest.state)) {
    return {
      ...base,
      headline: 'A check is running.',
      detail: 'Open it to see which agents have a recorded run. Nothing here is guessed ahead of those records.',
      action: { label: 'View the run', href: `/projects/${input.projectId}/assessments/${latest.id}` },
    };
  }
  if (latest.state === 'AWAITING_APPROVAL') {
    return {
      ...base,
      headline: 'A check is paused for a human decision.',
      detail: 'Approving lets a candidate fix be built and re-tested. Nothing is merged or deployed.',
      action: { label: 'Review the proposed fix', href: `/projects/${input.projectId}/approvals` },
    };
  }
  if (latest.state === 'FAILED' || latest.state === 'BUDGET_EXHAUSTED' || latest.state === 'CANCELLED') {
    return {
      ...base,
      headline: latest.state === 'FAILED' ? 'The latest check failed.' : `The latest check is ${latest.state === 'CANCELLED' ? 'cancelled' : 'out of budget'}.`,
      detail: 'Open the run for the recorded error. This is not a clean result.',
      action: { label: 'View the run', href: `/projects/${input.projectId}/assessments/${latest.id}` },
    };
  }
  const open = codeOpen + securityOpen;
  return {
    ...base,
    headline: open === 0 ? 'The latest check finished. No open findings are in this list.' : `The latest check finished. ${open} open finding${open === 1 ? '' : 's'} still need a look.`,
    detail: 'Verified means independent tests accepted a candidate fix. It does not mean the whole application is secure.',
    action: { label: 'View results', href: `/projects/${input.projectId}/findings` },
  };
}
