'use client';

import Link from 'next/link';
import { useState } from 'react';
import type { Repository } from '@hackatl/frontend-transport';
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
    <header className="commit-intro"><p className="network-eyebrow">CHANGE → INVESTIGATE → VERIFY</p><h1>Every change has a story.</h1><p>Choose a commit. Follow the code reviewer, then the seven security agents. Open a recorded run to see their tools, findings and evidence.</p></header>
    {!repos.length && <Empty>Connect a repository from Overview to see its commits.</Empty>}
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
      <ol className="commit-chapters"><li><b>01</b><span><strong>Understand the change</strong><small>The code reviewer reads the code and tests what it should do.</small></span></li><li><b>02</b><span><strong>Meet the security team</strong><small>Scout → Probe → Trace → Diagnose → Patch → Verify → Fortify.</small></span></li><li><b>03</b><span><strong>See the proof</strong><small>Inspect tool calls, affected code, test results and proposed fixes.</small></span></li></ol>
      {sha && records.status === 'loading' && <Loading label="Finding recorded runs" />}
      {sha && records.status === 'error' && <ErrorState error={records.error} onRetry={records.reload} />}
      {sha && records.status === 'ready' && <>
        {runs.map(run => <Link key={run.id} className="commit-run" href={`/projects/${projectId}/assessments/${run.id}`}><span>Open reviewer & agent journey<small><Mono>{run.id}</Mono></small></span><Badge view={ASSESSMENT_STATE[run.state]} /><span aria-hidden="true">↗</span></Link>)}
        {runs[0] && <RecordedTeam key={runs[0].id} assessmentId={runs[0].id} />}
        {!runs.length && <p className="text-sm text-muted">No matching run in the loaded history. Start an authorized analysis to create one.</p>}
        {(records.data.snapshots.next_cursor || records.data.assessments.next_cursor) && <p className="text-xs text-muted">Showing up to 100 recent snapshots and the latest assessment page; older runs may not appear here.</p>}
        {records.refreshError !== undefined && <p role="status" className="text-xs text-warn">Could not refresh. These are the last loaded records.</p>}
        <Link className="commit-analyze" href={`/projects/${projectId}/simulate?repo=${encodeURIComponent(repo.full_name)}&sha=${sha}`}>Analyze this commit <span aria-hidden="true">→</span></Link>
      </>}
    </div></div>
  </section>;
}

function RecordedTeam({ assessmentId }: { assessmentId: string }) {
  const runs = useResource(`commit-run:${assessmentId}`, signal => api().agentRuns(assessmentId, { signal }), 10000);
  if (runs.status === 'loading') return <Loading label="Opening the recorded agent work" />;
  if (runs.status === 'error') return <ErrorState error={runs.error} onRetry={runs.reload} />;
  return <div className="commit-recorded-team"><p className="network-eyebrow">LATEST MATCHING RUN · RECORDED WORK</p><h4>See what each agent did.</h4><p className="text-xs text-muted">Select a worker to inspect its recorded tools and handoff. A worker with no run is shown as not run.</p>{runs.refreshError !== undefined && <p role="status" className="text-xs text-warn">Refresh failed; showing the last loaded agent records.</p>}<AgentTeam runs={runs.data.items} /></div>;
}
