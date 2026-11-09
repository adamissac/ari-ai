'use client';

import type { AccessibleRepository } from '@hackatl/frontend-transport';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useState } from 'react';
import { Avatar } from '@/components/demo/ui';
import { Empty, ErrorState, Loading, PageTitle, inputClass } from '@/components/ui';
import { SetupLayout } from '@/components/onboarding/stepper';
import { api } from '@/lib/api';
import { claimRepo, connectRepo, projectForRepository, takenElsewhere } from '@/lib/github-connect';
import { groupByOrg, repoName } from '@/lib/github-orgs';
import { useResource } from '@/lib/use-resource';

/** Second step: choose a repository in the organization. */
export default function ConnectReposPage() {
  const { org: raw } = useParams<{ org: string }>();
  const login = decodeURIComponent(raw);
  const router = useRouter();
  const list = useResource('github-repos', signal => api().githubRepositories({ signal }));
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [failed, setFailed] = useState<AccessibleRepository | null>(null);
  const [filter, setFilter] = useState('');

  const open = async (repo: AccessibleRepository, claim = false) => {
    setBusy(repo.full_name);
    setError(null);
    setFailed(repo);
    try {
      const repoId = claim ? await claimRepo(login, repo) : await connectRepo(login, repo);
      const projectId = await projectForRepository(repoId);
      router.push(projectId
        ? `/projects/${projectId}/setup?repo=${encodeURIComponent(repoId)}`
        : `/connect/${encodeURIComponent(login)}/${encodeURIComponent(repoName(repo.full_name))}`);
    } catch (err) { setError(err); setBusy(null); }
  };


  const org = list.status === 'ready' ? groupByOrg(list.data.items).find(o => o.login.toLowerCase() === login.toLowerCase()) : undefined;
  const query = filter.trim().toLowerCase();
  const repos = org?.repos.filter(repo => repo.full_name.toLowerCase().includes(query)) ?? [];

  return (
    <SetupLayout current={2} org={login}>
      <div className="min-w-0" data-testid="connect-repos">
        <nav aria-label="Breadcrumb" className="mb-5 text-sm text-muted">
          <Link href="/connect" className="hover:text-ink">Organizations</Link><span aria-hidden="true" className="mx-2">/</span><span className="text-ink">{login}</span>
        </nav>
        <PageTitle title={<span className="flex items-center gap-3"><Avatar login={login} size={32} /><span>{login}</span></span>} subtitle="Choose a repository to review its changes" />
        {list.status === 'loading' && <Loading label="Loading repositories" />}
        {list.status === 'error' && <ErrorState error={list.error} onRetry={list.reload} context="Could not list your GitHub repositories" />}
        {list.status === 'ready' && !org && (
          <p className="text-sm text-muted" data-testid="connect-org-missing">No repositories from {login} are available to you. <Link className="text-brand hover:underline" href="/connect">Choose another organization</Link>.</p>
        )}
        {org && (
          <>
            <div className="mb-3 flex items-center justify-between gap-4">
              <input aria-label="Filter repositories" placeholder="Filter repositories" className={`${inputClass} w-full sm:max-w-xs`} value={filter} onChange={event => setFilter(event.target.value)} />
              <p className="shrink-0 font-mono text-xs tabular-nums text-muted" data-testid="connect-repo-count">{query ? `${repos.length} of ${org.repos.length}` : `${org.repos.length} ${org.repos.length === 1 ? 'repository' : 'repositories'}`}</p>
            </div>
            {repos.length === 0 ? (
              <Empty>No repositories match &quot;{filter}&quot;</Empty>
            ) : (
              <ul className="flex min-w-0 flex-col divide-y divide-line overflow-hidden rounded-xl border border-line bg-panel">
                {repos.map(repo => {
                  const name = repoName(repo.full_name);
                  return (
                    <li key={repo.full_name} data-testid={`connect-repo-${repo.full_name}`}>
                      <button type="button" className="group grid w-full min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 px-4 py-3 text-left transition-colors hover:bg-panel-2 disabled:opacity-60 xl:grid-cols-[minmax(0,1fr)_7rem_4rem_9rem_9rem] sm:px-5 xl:py-4" disabled={busy !== null} onClick={() => void open(repo)}>
                        {/* One row of aligned columns on desktop; name over a meta line on phones, so every row is the same height. */}
                        <span className="min-w-0 xl:contents">
                          <span className="block min-w-0 truncate font-medium xl:col-start-1" title={name.length > 32 ? repo.full_name : undefined}>{name}</span>
                          <span className="mt-1 flex min-w-0 items-center gap-3 text-xs text-muted xl:contents">
                            {repo.connected_repo_id && (
                              <span className={`flex items-center gap-2 xl:col-start-2 ${repo.disconnected ? '' : 'text-ink'}`}>
                                <span aria-hidden="true" className={`size-1.5 shrink-0 rounded-full ${repo.disconnected ? 'border border-faint' : 'bg-ok'}`} />
                                <span>{repo.disconnected ? 'Disconnected' : 'Connected'}</span>
                              </span>
                            )}
                            <span className="xl:col-start-3">{repo.private ? 'private' : 'public'}</span>
                            <span className="min-w-0 truncate font-mono xl:col-start-4">{repo.default_branch}</span>
                          </span>
                        </span>
                        <span className="flex items-center justify-end gap-2 whitespace-nowrap text-sm text-muted transition-colors group-hover:text-ink xl:col-start-5">
                          <span>{busy === repo.full_name ? 'Connecting…' : !repo.connected_repo_id ? 'Connect' : repo.disconnected ? 'Reconnect' : 'Continue setup'}</span>
                          <span aria-hidden="true" className="transition-colors group-hover:text-brand">→</span>
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </>
        )}
        {list.status === 'ready' && list.data.live_checked === false && (<p className="mt-3 text-xs text-muted" data-testid="repo-access-unverified">Access shown is from your last GitHub sign-in. Ari confirms access with GitHub when you connect.</p>)}
        {error !== null && <div className="mt-3"><ErrorState error={error} context="Could not connect the repository" /></div>}
        {failed && takenElsewhere(error) && (
          <div className="mt-3 rounded-xl border border-line bg-panel p-4 text-sm" data-testid="claim-repo">
            <p className="text-muted">Another Ari project already has <span className="font-mono text-ink">{failed.full_name}</span> connected. If you are an admin of this repository on GitHub, you can take it over: the other project is disconnected (its history is kept) and the repository connects here.</p>
            <button type="button" className="mt-3 rounded-lg bg-brand px-4 py-2 font-medium text-on-brand hover:bg-brand-deep disabled:opacity-50" disabled={busy !== null} onClick={() => void open(failed, true)}>{busy ? 'Claiming…' : 'Claim it (GitHub admins only)'}</button>
          </div>
        )}
      </div>
    </SetupLayout>
  );
}
