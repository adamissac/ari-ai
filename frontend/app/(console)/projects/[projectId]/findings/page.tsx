'use client';

import Link from 'next/link';
import { useState } from 'react';
import { useProject } from '@/components/project';
import { Async, Badge, Button, Empty, Mono, PageTitle, Panel, Time } from '@/components/ui';
import { api } from '@/lib/api';
import { findingBucket, OPEN_REASON } from '@/lib/findings';
import { shortSha } from '@/lib/format';
import { FINDING_STATUS, SEVERITY } from '@/lib/status';
import { useResource } from '@/lib/use-resource';

const TABS = [
  ['confirmed', 'Needs a fix'],
  ['fixed', 'Fixed'],
  ['unconfirmed', 'Not proven'],
  ['dismissed', 'Ruled out'],
] as const;
type Tab = (typeof TABS)[number][0];

const NOTE: Record<Tab, string> = {
  confirmed: 'A test Ari ran proved each of these is real. None has a fix that passed independent tests yet; the breakdown says where each one stopped.',
  fixed: "Ari's fix for each of these passed independent tests.",
  unconfirmed: "The code reviewer or the 7 agents flagged these while reviewing a commit, but no test proved them (or the test could not decide). The same suspicion raised on several commits is listed once. No action needed unless one looks real.",
  dismissed: 'A test showed the problem is not there, or someone accepted the risk or closed it.',
};

/** Untested suspicions and undecided tests share one tab: neither is a confirmed problem. */
function tabOf(status: string): Tab {
  const bucket = findingBucket(status);
  return bucket === 'untested' || bucket === 'inconclusive' ? 'unconfirmed' : bucket;
}

export default function FindingsPage() {
  const { project, selectedRepo } = useProject();
  const findings = useResource(selectedRepo ? `findings:${project.id}:${selectedRepo.id}` : null, s => api().findings(project.id, { signal: s, repoId: selectedRepo!.id }));
  const assessments = useResource(selectedRepo ? `findings-assessments:${project.id}:${selectedRepo.id}` : null, s => api().assessments(project.id, { signal: s, repoId: selectedRepo!.id }));
  const approvals = useResource(selectedRepo ? `findings-approvals:${project.id}:${selectedRepo.id}` : null, s => api().approvals(project.id, { signal: s, repoId: selectedRepo!.id }), 15000);
  const authority = useResource(`delivery-authority:${project.id}`, s => api().deliveryAuthority(project.id, { signal: s }), 30000);
  const pendingIds = new Set(approvals.status === 'ready' ? approvals.data.items.filter(a => a.subject_type === 'remediation' && a.status === 'pending').map(a => a.subject_id) : []);
  const waiting = approvals.status === 'ready' ? approvals.data.items.filter(a => a.subject_type === 'remediation' && a.status === 'pending').length : 0;
  const automatic = authority.status === 'ready' && authority.data.state === 'active';
  const [tab, setTab] = useState<Tab>('confirmed');
  const counts = findings.status === 'ready' ? collapse(findings.data.items).reduce<Record<Tab, number>>((n, g) => { n[tabOf(g.status)]++; return n; }, { confirmed: 0, fixed: 0, unconfirmed: 0, dismissed: 0 }) : null;
  return (
    <div className="flex min-w-0 flex-col gap-6">
      <PageTitle title="Findings" subtitle={selectedRepo?.full_name ?? 'No repository connected'} />
      {!selectedRepo && <Empty>No repository connected. <Link className="text-brand hover:underline" href={`/projects/${project.id}/settings#connect-repo`}>Connect a repository</Link>.</Empty>}
      {selectedRepo && waiting > 0 && (
        <div role="status" data-testid="findings-approval-banner" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-warn/40 bg-warn/10 px-4 py-3 text-sm">
          <p><span className="font-medium text-ink">{waiting} fix{waiting === 1 ? ' is' : 'es are'} waiting for your approval.</span> Ari has proven the problem and planned the fix, but does not write it until you approve.{!automatic && ' To stop being asked, turn on automatic fix delivery in Settings.'}</p>
          <span className="flex flex-wrap gap-3">
            <Link className="inline-flex items-center rounded-lg bg-brand px-4 py-2 font-medium text-on-brand hover:bg-brand-deep" href={`/projects/${project.id}/approvals?repo=${encodeURIComponent(selectedRepo.id)}`}>Approve fixes</Link>
            {!automatic && <Link className="inline-flex items-center text-brand hover:underline" href={`/projects/${project.id}/settings`}>Settings</Link>}
          </span>
        </div>
      )}
      {selectedRepo && <Panel title="Findings">
      <div role="tablist" aria-label="Finding groups" className="mb-3 flex flex-wrap gap-1">
        {TABS.map(([t, label]) => (
          <button key={t} role="tab" type="button" aria-selected={tab === t} onClick={() => setTab(t)}
            className={`rounded-md px-3 py-1.5 text-sm ${tab === t ? 'bg-panel-2 text-ink ring-1 ring-accent/50' : 'text-muted hover:text-ink'}`}>{label}{counts && <span className="ml-1.5 tabular-nums text-faint">{counts[t]}</span>}</button>
        ))}
      </div>
      <p className="mb-3 text-sm text-muted" data-testid="finding-group-note">{NOTE[tab]}</p>
      {findings.status === 'ready' && <TabBreakdown tab={tab} items={collapse(findings.data.items)} pendingIds={pendingIds} />}
      <Async resource={findings} label="findings">
        {page => {
          const repoItems = page.items;
          const items = collapse(repoItems).filter(f => tabOf(f.status) === tab);
          if (repoItems.length === 0 && assessments.status === 'ready' && assessments.data.items.length === 0) {
            return (
              <div data-testid="findings-no-review">
                <Empty>Ari has not reviewed {selectedRepo.full_name} yet, so there are no findings. Findings appear here after the first review finishes.</Empty>
                <div className="mt-3 flex justify-center">
                  <Link className="inline-flex items-center rounded-lg bg-brand px-4 py-2 text-sm font-medium text-on-brand hover:bg-brand-deep" href={`/projects/${project.id}/commits?repo=${encodeURIComponent(selectedRepo.id)}#start-assessment`}>Run a review</Link>
                </div>
              </div>
            );
          }
          if (items.length === 0 && tab === 'confirmed' && counts && counts.fixed > 0) {
            return (
              <>
                <Empty>Nothing needs a fix. {counts.fixed} fixed.</Empty>
                <div className="mt-3 flex justify-center">
                  <Button variant="primary" onClick={() => setTab('fixed')}>View fixed findings</Button>
                </div>
              </>
            );
          }
          if (items.length === 0) return <Empty>{tab === 'unconfirmed' ? 'Nothing unproven.' : tab === 'dismissed' ? 'Nothing ruled out.' : tab === 'fixed' ? 'No fix has been accepted by independent tests yet.' : 'Nothing needs a fix.'}</Empty>;
          return (
            <>
              <div className="hidden min-w-0 overflow-x-auto sm:block" data-testid="findings-table-scroll">
                <table className="w-full min-w-[640px] text-left text-sm">
                  <thead className="text-xs tracking-wider text-faint">
                    <tr><th className="py-1.5 pr-3">Finding</th><th className="pr-4">Status</th><th className="pr-3">Severity</th><th className="pr-3">Commit</th><th>Updated</th></tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {items.map(f => (
                      <tr key={f.id}>
                        <td className="py-2 pr-3"><Link className="hover:text-accent" href={`/projects/${project.id}/findings/${f.id}?repo=${encodeURIComponent(selectedRepo.id)}`}>{f.title}</Link>{f.repeats > 0 && <span className="ml-2 whitespace-nowrap text-xs text-faint" data-testid="finding-repeats">also on {f.repeats} earlier review{f.repeats === 1 ? '' : 's'}</span>}</td>
                        <td className="whitespace-nowrap pr-4">{pendingIds.has(f.id) ? <Badge view={WAITING} /> : <Badge view={FINDING_STATUS[f.status]} />}</td>
                        <td className="pr-3">{f.severity ? <Badge view={SEVERITY[f.severity.level]} /> : <span className="text-faint">—</span>}</td>
                        <td className="pr-3"><Mono>{shortSha(f.commit_sha)}</Mono></td>
                        <td className="text-muted"><Time iso={f.updated_at} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="flex min-w-0 flex-col gap-2 sm:hidden" data-testid="findings-mobile-list">
                {items.map(f => (
                  <article key={f.id} className="min-w-0 rounded-md border border-line bg-panel-2/40 p-3" data-testid="finding-mobile-row">
                    <Link className="block break-words hover:text-accent" href={`/projects/${project.id}/findings/${f.id}?repo=${encodeURIComponent(selectedRepo.id)}`}>{f.title}</Link>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <span data-testid="finding-mobile-status">{pendingIds.has(f.id) ? <Badge view={WAITING} /> : <Badge view={FINDING_STATUS[f.status]} />}</span>
                      {f.repeats > 0 && <span className="text-xs text-faint">also on {f.repeats} earlier review{f.repeats === 1 ? '' : 's'}</span>}
                      {f.severity && <Badge view={SEVERITY[f.severity.level]} />}
                      <Mono>{shortSha(f.commit_sha)}</Mono>
                      <span className="text-xs text-muted"><Time iso={f.updated_at} /></span>
                    </div>
                  </article>
                ))}
              </div>
            </>
          );
        }}
      </Async>
    </Panel>
      }
    </div>
  );
}

const WAITING = { label: 'Waiting for your approval', tone: 'warn', glyph: '⏸' } as const;

/**
 * Every commit's review saves its own copy of a finding, so the same title repeats. Show the
 * newest copy once (the API returns newest first) and say how many older reviews raised it.
 * shortcut: matches on exact title only, so reworded repeats stay separate; replace with a
 * backend fingerprint when findings get one.
 */
function collapse<T extends { title: string; status: string }>(items: readonly T[]): (T & { repeats: number })[] {
  const seen = new Map<string, T & { repeats: number }>();
  for (const f of items) {
    const key = `${tabOf(f.status)}\u0000${f.title}`;
    const first = seen.get(key);
    if (first) first.repeats++; else seen.set(key, { ...f, repeats: 0 });
  }
  return [...seen.values()];
}

/** Why the proven problems in the Needs a fix tab are still open. */
function TabBreakdown({ tab, items, pendingIds }: { tab: Tab; items: readonly { id: string; status: string }[]; pendingIds: ReadonlySet<string> }) {
  if (tab !== 'confirmed') return null;
  const reasons = new Map<string, number>();
  for (const f of items) {
    if (tabOf(f.status) !== tab) continue;
    const reason = pendingIds.has(f.id) ? 'waiting for your approval before Ari writes the fix' : OPEN_REASON[f.status] ?? f.status;
    reasons.set(reason, (reasons.get(reason) ?? 0) + 1);
  }
  if (!reasons.size) return null;
  return (
    <ul className="mb-3 flex flex-col gap-0.5 text-sm text-muted" data-testid="finding-group-breakdown">
      {[...reasons].sort((a, b) => b[1] - a[1]).map(([reason, n]) => <li key={reason}><span className="tabular-nums text-ink">{n}</span> {reason}</li>)}
    </ul>
  );
}
