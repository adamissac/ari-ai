'use client';

import type { AgentRun, Assessment, Approval, Finding } from '@hackatl/frontend-transport';
import Link from 'next/link';
import { Mono, Panel } from '@/components/ui';
import { coverage, outcomeCounts, stoppedExplanation } from '@/lib/assessment-outcome';
import { shortSha } from '@/lib/format';
import type { RelayItem } from '@/lib/relay';

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

/**
 * The answer to "what did this check do?" once it has stopped: a plain outcome for a
 * completed run, or why it did not finish and how to recover. Pending and running
 * checks render nothing here; the relay and phases already show live progress.
 */
export function AssessmentOutcome({
  assessment, findings, runs, approvals, relay, skipNote, projectId,
}: {
  assessment: Assessment;
  findings: readonly Finding[];
  runs: readonly AgentRun[];
  approvals: readonly Approval[] | null;
  relay: readonly RelayItem[];
  skipNote: string | null;
  projectId: string;
}) {
  const a = assessment;
  const retry = `/projects/${projectId}/commits?${new URLSearchParams({ ...(a.repo_id ? { repo: a.repo_id } : {}), commit: a.commit_sha }).toString()}#start-assessment`;

  if (a.state === 'FAILED' || a.state === 'CANCELLED' || a.state === 'BUDGET_EXHAUSTED') {
    const { cause, next } = stoppedExplanation(a.state, a.error?.code ?? null);
    const done = relay.flatMap(item => (item.kind === 'agent' && item.status === 'done' ? [item.label] : []));
    return (
      <Panel title="This check did not finish" className="mb-4">
        <div className="flex flex-col gap-3 p-4 text-sm" data-testid="assessment-outcome" data-outcome="stopped">
          <p><strong className="font-medium text-ink">What happened:</strong> <span className="text-muted">{cause}</span></p>
          <p className="text-muted">
            {done.length ? `Finished before it stopped: ${done.join(', ')}.` : 'No agent finished its step before it stopped.'}
            {' '}{findings.length ? `${plural(findings.length, 'finding')} recorded so far stay${findings.length === 1 ? 's' : ''} below.` : 'No findings were recorded.'}
            {' '}This is not a clean result.
          </p>
          <p><strong className="font-medium text-ink">What to do:</strong> <span className="text-muted">{next}</span></p>
          <div className="flex flex-wrap items-center gap-4">
            <Link href={retry} className="inline-flex h-9 items-center rounded-lg bg-brand px-3.5 text-sm font-medium text-on-brand hover:bg-brand-deep" data-testid="outcome-retry">Start a new check of commit {shortSha(a.commit_sha)}</Link>
            {(a.state === 'BUDGET_EXHAUSTED' || a.error?.code === 'BUDGET_EXHAUSTED') && <Link href={`/projects/${projectId}/settings`} className="text-sm text-brand hover:underline">Assessment budget in Settings →</Link>}
            {a.error?.code === 'SCOPE_DENIED' && <Link href={`/projects/${projectId}/scopes`} className="text-sm text-brand hover:underline">Authorized scopes →</Link>}
          </div>
          <p className="text-xs text-muted">Starting again uses your project&apos;s approved sandbox testing scope; you confirm it before anything runs.</p>
        </div>
      </Panel>
    );
  }

  if (a.state !== 'COMPLETED') return null;

  if (findings.length === 0) {
    const c = coverage(relay, runs, skipNote);
    return (
      <Panel title={c.kind === 'limited' ? 'No findings, limited coverage' : 'No findings recorded'} className="mb-4">
        <div className="flex flex-col gap-3 p-4 text-sm" data-testid="assessment-outcome" data-outcome={c.kind === 'limited' ? 'clean-limited' : 'clean'}>
          <p className="text-muted">
            This check of commit <Mono>{shortSha(a.commit_sha)}</Mono> recorded no issues.
            {' '}{c.kind === 'limited' ? 'Parts of the check did not run, so do not read this as a clean security result.' : 'That covers only this commit and what the agents below examined and tested. It is not proof that the application is secure.'}
          </p>
          <p><strong className="font-medium text-ink">What ran:</strong> <span className="text-muted">{c.ran.length ? c.ran.join(', ') : 'No agent finished a step.'}</span></p>
          {c.kind === 'limited' && (
            <div>
              <p className="font-medium text-ink">What was not covered:</p>
              <ul className="mt-1 list-disc pl-5 text-muted">{c.gaps.map(g => <li key={g}>{g}</li>)}</ul>
            </div>
          )}
        </div>
      </Panel>
    );
  }

  const n = outcomeCounts(findings, runs, approvals);
  const rows: { label: string; value: string }[] = [
    { label: 'Found', value: `${plural(n.findings, 'finding')}: ${n.confirmed} confirmed by an executed test, ${n.unconfirmed} not confirmed, ${n.ruledOut} ruled out.` },
    { label: 'Fix approval', value: approvals === null ? 'Could not load the approval records.' : n.approved + n.declined + n.pending === 0 ? 'No fix approval was requested.' : `${n.approved} approved, ${n.declined} declined, ${n.pending} waiting.` },
    { label: 'Fix proposed', value: n.fixesProposed ? `${plural(n.fixesProposed, 'candidate fix', 'candidate fixes')} written in an isolated copy.` : 'No fix was written.' },
    { label: 'Fix verified', value: n.fixesVerified ? `${n.fixesVerified} accepted by an independent re-test.` : 'No fix has passed an independent re-test.' },
    { label: 'Changed in your repository', value: 'Ari never merges pull requests or deploys. Whether a verified fix was delivered (as a pull request or commit, per your fix-delivery setting) is on each finding’s patch record.' },
  ];
  return (
    <Panel title="What this check did" className="mb-4">
      <dl className="grid grid-cols-1 divide-y divide-line text-sm" data-testid="assessment-outcome" data-outcome="findings">
        {rows.map(r => (
          <div key={r.label} className="grid grid-cols-1 gap-1 px-4 py-2.5 sm:grid-cols-[12rem_minmax(0,1fr)]">
            <dt className="font-medium text-ink">{r.label}</dt><dd className="text-muted">{r.value}</dd>
          </div>
        ))}
      </dl>
    </Panel>
  );
}
