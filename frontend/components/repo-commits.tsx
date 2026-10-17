'use client';

import type { Repository } from '@hackatl/frontend-transport';
import Link from 'next/link';
import { ErrorState, Loading, Mono, Time } from '@/components/ui';
import { api } from '@/lib/api';
import { useResource } from '@/lib/use-resource';

/** Recent commits on the default branch, read live from GitHub through the App installation. */
export function RepoCommits({ repo, onPick }: { repo: Repository; onPick: (sha: string) => void }) {
  const commits = useResource(`commits:${repo.id}`, signal => api().repositoryCommits(repo.id, { signal }));
  if (commits.status === 'loading') return <Loading label="Loading recent commits" />;
  if (commits.status === 'error') return <ErrorState error={commits.error} onRetry={commits.reload} context="Could not read commits from GitHub" />;
  const { items, available, reason } = commits.data;
  if (!available) return <p className="text-xs text-faint" data-testid="repo-commits-unavailable">{reason}</p>;
  if (items.length === 0) return <p className="text-xs text-faint">No commits on {repo.default_branch}.</p>;
  return (
    <section aria-label={`Recent commits in ${repo.full_name}`} data-testid="repo-commits">
      <p className="label-mono mb-1.5 text-faint">Recent commits · {repo.default_branch}</p>
      <ul className="flex flex-col divide-y divide-line rounded-md border border-line bg-panel">
        {items.slice(0, 10).map(c => (
          <li key={c.sha} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-sm">
            <span className="flex min-w-0 flex-1 flex-col">
              <button type="button" className="truncate text-left text-ink hover:text-brand" onClick={() => onPick(c.sha)}>{c.message}</button>
              <span className="text-xs text-muted">
                {c.author}{c.committed_at && <> · <Time iso={c.committed_at} /></>} · {c.html_url ? <a className="hover:text-brand" href={c.html_url} target="_blank" rel="noreferrer"><Mono>{c.sha.slice(0, 7)}</Mono></a> : <Mono>{c.sha.slice(0, 7)}</Mono>}
              </span>
            </span>
            <span className="flex items-center gap-3 text-xs">
              <button type="button" className="text-muted hover:text-ink" onClick={() => onPick(c.sha)}>Explore commit</button>
              <Link className="text-brand hover:underline" href={`/projects/${repo.project_id}/simulate?repo=${encodeURIComponent(repo.full_name)}&sha=${c.sha}`}>Analyze →</Link>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
