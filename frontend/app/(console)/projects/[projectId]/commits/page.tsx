'use client';

import Link from 'next/link';
import { useState } from 'react';
import type { AssessmentState, Repository } from '@hackatl/frontend-transport';
import { useProject } from '@/components/project';
import { AgentTeam } from '@/components/agent-team';
import { RepoCommits } from '@/components/repo-commits';
import { Badge, Empty, ErrorState, Loading, Mono } from '@/components/ui';
import { api } from '@/lib/api';
import { useResource } from '@/lib/use-resource';
import { ASSESSMENT_STATE } from '@/lib/status';

export default function CommitsPage() {
  const { project, repos } = useProject();
  return <div className="commit-workspace">
    <header className="commit-intro"><p className="network-eyebrow">Code review</p><h1>Review a change.</h1><p>Pick a commit to review its code, see findings, or open a recorded run.</p></header>
    {!repos.length && <Empty>Connect a repository from the 7 agents tab to see its commits.</Empty>}
    {repos.map(repo => <RepositoryHistory key={repo.id} repo={repo} projectId={project.id} />)}
  </div>;
}

function RepositoryHistory({ repo, projectId }: { repo: Repository; projectId: string }) {
  const [sha, setSha] = useState<string | null>(null);
  const records = useResource(`commit-history:${repo.id}`, async signal => {
    const [snapshots, assessments] = await Promise.all([
      api().snapshots(repo.id, { limit: 100 }, { signal }),
      api().assessments(projectId, { signal }),
    ]);
    return { snapshots, assessments };
  }, 10000);
  const snapshotIds = new Set(records.data?.snapshots.items.filter(s => s.commit_sha === sha).map(s => s.id));
  const runs = records.data?.assessments.items.filter(a => a.snapshot_id && snapshotIds.has(a.snapshot_id)) ?? [];
  return <section className="commit-repository" aria-label={`Commit stories for ${repo.full_name}`}>
    <header><span className="network-eyebrow">CONNECTED REPOSITORY</span><h2>{repo.full_name}</h2></header>
    <div className="commit-columns"><div><RepoCommits repo={repo} onPick={setSha} /></div><div className="commit-story" aria-live="polite">
      <p className="network-eyebrow">{sha ? `SELECTED CHANGE / ${sha.slice(0, 7)}` : 'START WITH A CHANGE'}</p>
      <h3>{sha ? 'Follow this commit through Ari.' : 'Pick a commit on the left.'}</h3>
      {sha && records.status === 'loading' && <Loading label="Finding recorded runs" />}
      {sha && records.status === 'error' && <ErrorState error={records.error} onRetry={records.reload} />}
      {sha && records.status === 'ready' && <>
        {runs.map(run => <Link key={run.id} className="commit-run" href={`/projects/${projectId}/assessments/${run.id}`}><span>Open reviewer & agent journey<small><Mono>{run.id}</Mono></small></span><Badge view={ASSESSMENT_STATE[run.state]} /><span aria-hidden="true">↗</span></Link>)}
        {runs[0] && <details className="project-detail"><summary>Agent activity</summary><RecordedTeam key={runs[0].id} assessmentId={runs[0].id} state={runs[0].state} /></details>}
        {!runs.length && <p className="text-sm text-muted">No matching run in the loaded history. Start an authorized analysis to create one.</p>}
        {(records.data.snapshots.next_cursor || records.data.assessments.next_cursor) && <p className="text-xs text-muted">Showing up to 100 recent snapshots and the latest assessment page; older runs may not appear here.</p>}
        {records.refreshError !== undefined && <p role="status" className="text-xs text-warn">Could not refresh. These are the last loaded records.</p>}
        <Link className="commit-analyze" href={`/connect/${repo.full_name.split('/').map(encodeURIComponent).join('/')}/commit/${sha}`}>Analyze this commit <span aria-hidden="true">→</span></Link>
      </>}
    </div></div>
  </section>;
}

function RecordedTeam({ assessmentId, state }: { assessmentId: string; state: AssessmentState }) {
  const runs = useResource(`commit-run:${assessmentId}`, signal => api().agentRuns(assessmentId, { signal }), 10000);
  if (runs.status === 'loading') return <Loading label="Opening the recorded agent work" />;
  if (runs.status === 'error') return <ErrorState error={runs.error} onRetry={runs.reload} />;
  return <div className="commit-recorded-team"><p className="network-eyebrow">LATEST MATCHING RUN · RECORDED WORK</p><h4>See what each agent did.</h4><p className="text-xs text-muted">Select a worker to inspect its recorded tools and handoff. A worker with no run is shown as not needed or not reached.</p>{runs.refreshError !== undefined && <p role="status" className="text-xs text-warn">Refresh failed; showing the last loaded agent records.</p>}<AgentTeam runs={runs.data.items} state={state} /></div>;
}
