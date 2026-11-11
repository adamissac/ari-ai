'use client';

import Link from 'next/link';
import { useState } from 'react';
import { useProject } from '@/components/project';
import { Async, Badge, Button, Empty, Mono, PageTitle, Panel, Time } from '@/components/ui';
import { api } from '@/lib/api';
import { findingBucket } from '@/lib/findings';
import { shortSha } from '@/lib/format';
import { FINDING_STATUS, SEVERITY } from '@/lib/status';
import { useResource } from '@/lib/use-resource';

const TABS = [
  ['confirmed', 'Confirmed'],
  ['fixed', 'Fixed'],
  ['unconfirmed', 'Unconfirmed'],
  ['dismissed', 'Dismissed'],
] as const;
type Tab = (typeof TABS)[number][0];

const NOTE: Record<Tab, string> = {
  confirmed: 'A test reproduced each of these. They need a fix.',
  fixed: 'Independent tests accepted the fix for each of these.',
  unconfirmed: 'Suspicions that no test has confirmed. Most need no action.',
  dismissed: 'Ruled out by a test, accepted, or closed.',
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
  const [tab, setTab] = useState<Tab>('confirmed');
  const counts = findings.status === 'ready' ? findings.data.items.reduce<Record<Tab, number>>((n, f) => { n[tabOf(f.status)]++; return n; }, { confirmed: 0, fixed: 0, unconfirmed: 0, dismissed: 0 }) : null;
  return (
    <div className="flex min-w-0 flex-col gap-6">
      <PageTitle title="Findings" subtitle={selectedRepo?.full_name ?? 'No repository connected'} />
      {!selectedRepo && <Empty>No repository connected. <Link className="text-brand hover:underline" href={`/projects/${project.id}/settings#connect-repo`}>Connect a repository</Link>.</Empty>}
      {selectedRepo && <Panel title="Findings">
      <div role="tablist" aria-label="Finding groups" className="mb-3 flex flex-wrap gap-1">
        {TABS.map(([t, label]) => (
          <button key={t} role="tab" type="button" aria-selected={tab === t} onClick={() => setTab(t)}
            className={`rounded-md px-3 py-1.5 text-sm ${tab === t ? 'bg-panel-2 text-ink ring-1 ring-accent/50' : 'text-muted hover:text-ink'}`}>{label}{counts && <span className="ml-1.5 tabular-nums text-faint">{counts[t]}</span>}</button>
        ))}
      </div>
      <p className="mb-3 text-sm text-muted" data-testid="finding-group-note">{NOTE[tab]}</p>
      <Async resource={findings} label="findings">
        {page => {
          const repoItems = page.items;
          const items = repoItems.filter(f => tabOf(f.status) === tab);
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
                <Empty>No confirmed problems are open. {counts.fixed} fixed.</Empty>
                <div className="mt-3 flex justify-center">
                  <Button variant="primary" onClick={() => setTab('fixed')}>View fixed findings</Button>
                </div>
              </>
            );
          }
          if (items.length === 0) return <Empty>{tab === 'unconfirmed' ? 'No unconfirmed suspicions.' : tab === 'dismissed' ? 'Nothing dismissed.' : tab === 'fixed' ? 'No fix has been accepted by independent tests yet.' : 'No confirmed problems.'}</Empty>;
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
                        <td className="py-2 pr-3"><Link className="hover:text-accent" href={`/projects/${project.id}/findings/${f.id}?repo=${encodeURIComponent(selectedRepo.id)}`}>{f.title}</Link></td>
                        <td className="whitespace-nowrap pr-4"><Badge view={FINDING_STATUS[f.status]} /></td>
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
                      <span data-testid="finding-mobile-status"><Badge view={FINDING_STATUS[f.status]} /></span>
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
