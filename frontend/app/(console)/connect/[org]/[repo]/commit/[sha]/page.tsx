'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useMemo } from 'react';
import { CommitAnalysis } from '@/components/demo/commit-analysis';
import { DemoMarker } from '@/components/demo/ui';
import { Empty, ErrorState, Loading } from '@/components/ui';
import { api } from '@/lib/api';
import { useAccessibleRepo } from '@/lib/real-repo';
import { simulatedAttack } from '@/lib/simulated-attack';
import { useResource } from '@/lib/use-resource';

/**
 * A real commit from the user's repository in the same view as /demo. The commit header is
 * real (from GitHub); the review and agent replay are illustrative (ADR 0013) until a live
 * assessment has run for it, and the page says so.
 */
export default function RealCommitPage() {
  const params = useParams<{ org: string; repo: string; sha: string }>();
  const org = decodeURIComponent(params.org);
  const name = decodeURIComponent(params.repo);
  const repo = useAccessibleRepo(org, name);
  const id = repo.status === 'ready' ? repo.data?.connected_repo_id ?? null : null;
  const commits = useResource(id ? `commits:${id}` : null, signal => api().repositoryCommits(id!, { signal }));
  const real = commits.status === 'ready' ? commits.data.items.find(c => c.sha === params.sha) : undefined;
  const sim = useMemo(() => (repo.status === 'ready' && repo.data && real ? simulatedAttack(repo.data.full_name, repo.data.default_branch, real) : null), [repo, real]);

  return (
    <div className="commit-stage" data-testid="real-commit">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <nav aria-label="Breadcrumb" className="flex flex-wrap items-center gap-1.5 text-sm">
          <Link href="/connect">Organizations</Link><span aria-hidden="true" className="text-white/30">/</span>
          <Link href={`/connect/${encodeURIComponent(org)}`}>{org}</Link><span aria-hidden="true" className="text-white/30">/</span>
          <Link href={`/connect/${encodeURIComponent(org)}/${encodeURIComponent(name)}`}>{name}</Link><span aria-hidden="true" className="text-white/30">/</span>
          <span className="font-semibold">{params.sha.slice(0, 7)}</span>
        </nav>
        <details className="amap-more text-right" data-testid="real-commit-note">
          <summary><DemoMarker /> What is real here?</summary>
          <p className="mt-2 max-w-sm text-left text-xs text-white/60">The commit, author and time come from GitHub. The review and agent replay are an illustrative run on this commit; nothing in your repository was attacked.</p>
        </details>
      </div>
      {(repo.status === 'loading' || commits.status === 'loading') && <Loading label="Loading the commit" />}
      {repo.status === 'error' && <ErrorState error={repo.error} onRetry={repo.reload} />}
      {commits.status === 'error' && <ErrorState error={commits.error} onRetry={commits.reload} context="Could not read the commit from GitHub" />}
      {repo.status === 'ready' && (!repo.data || !id) && <Empty>Connect {org}/{name} first.</Empty>}
      {commits.status === 'ready' && !real && <Empty>This commit is not among the latest commits on the default branch.</Empty>}
      {sim && <CommitAnalysis key={sim.commit.sha} repo={sim.repo} commit={sim.commit} />}
    </div>
  );
}
