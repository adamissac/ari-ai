'use client';

import type { AccessibleRepository } from '@hackatl/frontend-transport';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useState } from 'react';
import { Avatar } from '@/components/demo/ui';
import { Empty, ErrorState, Field, Loading, PageTitle, Tag, inputClass } from '@/components/ui';
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
        <PageTitle eyebrow="Repositories / 02" title={<span className="flex items-center gap-4"><Avatar login={login} size={40} /><span>{login}</span></span>} subtitle="Select a repository to review its changes. Connecting opens setup. No check runs until you approve sandbox testing and start one." />
        {error !== null && <div className="mb-4" data-testid="connect-repo-error"><ErrorState error={error} context="Could not connect the repository" /></div>}
        {failed && takenElsewhere(error) && (
          <div className="mb-4 rounded-xl border border-line bg-panel p-4 text-sm" data-testid="claim-repo">
            <p className="text-muted">Another Ari project already has <span className="font-mono text-ink">{failed.full_name}</span> connected. If you are an admin of this repository on GitHub, you can take it over: the other project is disconnected (its history is kept) and the repository connects here.</p>
            <button type="button" className="mt-3 rounded-lg bg-brand px-4 py-2 font-medium text-on-brand hover:bg-brand-deep disabled:opacity-50" disabled={busy !== null} onClick={() => void open(failed, true)}>{busy ? 'Claiming…' : 'Claim it (GitHub admins only)'}</button>
          </div>
        )}
        {list.status === 'loading' && <Loading label="Loading repositories" />}
        {list.status === 'error' && <ErrorState error={list.error} onRetry={list.reload} context="Could not list your GitHub repositories" />}
        {list.status === 'ready' && !org && (
          <p className="text-sm text-muted" data-testid="connect-org-missing">No repositories from {login} are available to you. <Link className="text-brand hover:underline" href="/connect">Choose another organization</Link>.</p>
        )}
        {org && (
          <>
            <div className="mb-4 max-w-xl">
              <Field label="Filter repositories">
                <input className={inputClass} value={filter} onChange={event => setFilter(event.target.value)} />
              </Field>
            </div>
            {repos.length === 0 ? (
              <Empty>No repositories match &quot;{filter}&quot;</Empty>
            ) : (
              <ul className="flex min-w-0 flex-col divide-y divide-line overflow-hidden rounded-2xl border border-line bg-panel">
                {repos.map(repo => {
                  const name = repoName(repo.full_name);
                  return (
                    <li key={repo.full_name} data-testid={`connect-repo-${repo.full_name}`}>
                      <button type="button" className="group flex w-full min-w-0 flex-wrap items-center justify-between gap-3 px-4 py-4 text-left transition-colors hover:bg-panel-2 disabled:opacity-60 sm:px-5" disabled={busy !== null} onClick={() => void open(repo)}>
                        <span className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
                          <span className="min-w-0 max-w-[min(54vw,32rem)] truncate font-semibold group-hover:text-brand" title={name.length > 32 ? repo.full_name : undefined}>{name}</span>
                          <Tag>{repo.private ? 'private' : 'public'}</Tag>
                          {repo.connected_repo_id && (repo.disconnected ? <Tag>Disconnected</Tag> : <Tag tone="info">Connected</Tag>)}
                        </span>
                        <span className="flex shrink-0 items-center gap-2 text-sm text-muted">
                          <span className="font-mono text-xs">{repo.default_branch}</span>
                          <span>{busy === repo.full_name ? 'Connecting…' : !repo.connected_repo_id ? 'Connect' : repo.disconnected ? 'Reconnect' : 'Continue setup'}</span>
                          <span aria-hidden="true">→</span>
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </>
        )}
        {list.status === 'ready' && list.data.live_checked === false && (<p className="mt-2 text-xs text-muted" data-testid="repo-access-unverified">Access shown is from your last GitHub sign-in. Ari confirms access with GitHub when you connect.</p>)}
      </div>
    </SetupLayout>
  );
}
