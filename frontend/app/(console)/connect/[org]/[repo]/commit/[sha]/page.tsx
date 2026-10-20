'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { CommitAnalysis } from '@/components/demo/commit-analysis';
import { CommitRunWorkspace } from '@/components/commit-run-workspace';
import { RealAssessmentPanel } from '@/components/real-assessment-panel';
import { Empty, ErrorState, Loading } from '@/components/ui';
import type { DemoCommit, DemoRepo } from '@/lib/demo/data';
import type { LiveResult } from '@/lib/live-analysis';
import { minutesSince } from '@/lib/simulated-attack';
import { useAccessibleRepo } from '@/lib/real-repo';
import { useResource } from '@/lib/use-resource';
import { api } from '@/lib/api';

type QuickRead = { key: string; data?: LiveResult; error?: string };

export default function RealCommitPage() {
  const params = useParams<{ org: string; repo: string; sha: string }>();
  const org = decodeURIComponent(params.org);
  const name = decodeURIComponent(params.repo);
  const repo = useAccessibleRepo(org, name);
  if (repo.status === 'loading') return <Loading label="Loading the repository" />;
  if (repo.status === 'error') return <ErrorState error={repo.error} onRetry={repo.reload} />;
  if (!repo.data) return <Empty>{org}/{name} is not reachable through your GitHub App installation.</Empty>;
  return <SelectedCommit key={`${repo.data.full_name}:${params.sha}`} org={org} name={name} sha={params.sha} repo={repo.data} onConnected={repo.reload} />;
}

function SelectedCommit({ org, name, sha, repo, onConnected }: {
  org: string; name: string; sha: string; repo: NonNullable<ReturnType<typeof useAccessibleRepo>['data']>; onConnected: () => void;
}) {
  const [connectedRepoId, setConnectedRepoId] = useState(repo.connected_repo_id);
  const metadata = useResource(connectedRepoId ? `selected-commit:${connectedRepoId}:${sha}` : null, signal => api().repositoryCommits(connectedRepoId!, { signal }));
  const selectedCommit = metadata.data?.items.find(commit => commit.sha === sha);
  const [assessmentId, setAssessmentId] = useState<string | null>(null);
  const [request, setRequest] = useState(0);
  const [quick, setQuick] = useState<QuickRead | null>(null);
  const identity = `${repo.full_name}:${sha}:${request}`;
  useEffect(() => {
    if (!request) return;
    const ctrl = new AbortController();
    fetch('/api/analyze', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ repo: repo.full_name, sha }), signal: ctrl.signal })
      .then(async res => {
        const body = await res.json().catch(() => null);
        if (!res.ok) throw new Error(body?.error?.message ?? `Quick read failed (${res.status}).`);
        if (body.commit.sha !== sha) throw new Error('The response does not match this commit.');
        if (!ctrl.signal.aborted) setQuick({ key: identity, data: body as LiveResult });
      }).catch((err: unknown) => { if (!ctrl.signal.aborted) setQuick({ key: identity, error: err instanceof Error ? err.message : 'Quick read failed.' }); });
    return () => ctrl.abort();
  }, [request, repo.full_name, sha, identity]);
  const live = quick?.key === identity ? quick : null;
  const view = useMemo(() => {
    if (!live?.data) return null;
    const data = live.data;
    const commit: DemoCommit = { sha, message: data.commit.message, body: data.commit.body, author: data.commit.author, minutesAgo: minutesSince(data.commit.committedAt), branch: repo.default_branch, ci: 'pending', verdict: data.verdict, scenario: 'clean', files: data.commit.files, additions: data.commit.additions, deletions: data.commit.deletions };
    const demoRepo: DemoRepo = { org, name, description: '', language: '', visibility: repo.private ? 'private' : 'public', defaultBranch: repo.default_branch, stars: 0, components: data.components, links: data.links, commits: [commit] };
    return { commit, repo: demoRepo, analysis: data.analysis, live: { model: data.model, truncated: data.truncated, htmlUrl: data.commit.htmlUrl } };
  }, [live, sha, repo.default_branch, repo.private, org, name]);
  const base = `/connect/${encodeURIComponent(org)}/${encodeURIComponent(name)}`;
  return <div className="commit-stage" data-testid="real-commit">
    <nav aria-label="Breadcrumb" className="mb-6 flex flex-wrap items-center gap-2 text-sm text-white/65">
      <Link href="/connect">Organizations</Link><span aria-hidden="true">/</span><Link href={`/connect/${encodeURIComponent(org)}`}>{org}</Link><span aria-hidden="true">/</span><Link href={base}>{name}</Link><span aria-hidden="true">/</span><span>{sha.slice(0, 7)}</span>
    </nav>
    <header className="mb-6"><p className="label-mono text-white/50">{repo.full_name}</p><h1 className="mt-3 text-3xl font-semibold">{selectedCommit?.message ?? `Commit ${sha.slice(0, 7)}`}</h1><p className="mt-2 text-sm text-white/60">Code review, seven agents, and recorded replay for this change.</p>{selectedCommit?.html_url && /^https?:\/\//.test(selectedCommit.html_url) && <a className="mt-3 inline-block text-xs text-white/65 underline" href={selectedCommit.html_url} target="_blank" rel="noreferrer">View commit on GitHub ↗</a>}</header>
    <RealAssessmentPanel org={org} repo={{ ...repo, connected_repo_id: connectedRepoId }} sha={sha} onConnected={id => { setConnectedRepoId(id); onConnected(); }} onRunSelected={setAssessmentId} />
    <CommitRunWorkspace assessmentId={assessmentId} repoId={connectedRepoId} sha={sha} fullName={repo.full_name} quickRead={<details className="mt-6 border-t border-white/10 pt-4"><summary>Optional quick read</summary><p className="mt-3 text-xs text-white/55" data-testid="real-commit-provenance" title="The diff comes from GitHub. This is one Claude call, not an executed assessment.">Quick read · nothing executed</p><button type="button" className="mt-3 rounded-full bg-white/10 px-4 py-2 text-sm" disabled={request > 0 && !live} onClick={() => setRequest(n => n + 1)}>{request > 0 && !live ? 'Reading…' : 'Read this diff'}</button>{live?.error && <p role="alert" className="mt-3 text-sm">{live.error}</p>}{view && <div className="mt-4"><CommitAnalysis {...view} reviewOnly /></div>}</details>} />
  </div>;
}
