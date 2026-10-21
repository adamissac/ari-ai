'use client';

import Link from 'next/link';
import { Avatar, GitHubMark } from '@/components/demo/ui';
import { BRAND_NAME } from '@/components/brand';
import { ErrorState, Loading } from '@/components/ui';
import { RefreshFromGitHub } from '@/components/refresh-from-github';
import { api } from '@/lib/api';
import { groupByOrg } from '@/lib/github-orgs';
import { useResource } from '@/lib/use-resource';

/** After GitHub sign-in: choose the organization (App installation account) to work in. */
export default function ConnectOrgsPage() {
  const list = useResource('github-repos', signal => api().githubRepositories({ signal }));

  return (
    <div className="workspace-index mx-auto max-w-5xl px-4 py-8" data-testid="connect-orgs">
      <header className="workspace-heading mb-6">
        <p className="workspace-eyebrow">Your workspace / 01</p>
        <h1 className="text-3xl font-semibold tracking-tight">Organizations</h1>
        <div className="workspace-heading-bottom"><p>Choose an organization to see its repositories.</p><RefreshFromGitHub className="mt-1 text-sm" /></div>
      </header>
      {list.status === 'loading' && <Loading label="Loading your GitHub organizations" />}
      {list.status === 'error' && <ErrorState error={list.error} onRetry={list.reload} context="Could not list your GitHub repositories" />}
      {list.status === 'ready' && (() => {
        const orgs = groupByOrg(list.data.items);
        const install = list.data.install_url;
        return (
          <>
            {orgs.length === 0 ? (
              <div className="rounded-2xl border border-line bg-panel p-8 text-center" data-testid="connect-empty">
                <GitHubMark className="mx-auto h-8 w-8 text-ink" />
                <h2 className="mt-3 text-lg font-semibold">No repositories yet</h2>
                <p className="mx-auto mt-1.5 max-w-md text-sm text-muted">Install the {BRAND_NAME} GitHub App on an organization or your account.</p>
                {install && <a href={install} className="mt-5 inline-flex h-10 items-center gap-2 rounded-lg bg-[#1c1210] px-4 text-sm font-medium text-white hover:bg-brand"><GitHubMark />Install the GitHub App</a>}
              </div>
            ) : (
              <ul className="grid gap-3 md:grid-cols-3">
                {orgs.map((org, i) => (
                  <li key={org.login} className="demo-rise" style={{ ['--i' as string]: i }}>
                    <Link href={`/connect/${encodeURIComponent(org.login)}`} className="workspace-org-card demo-card group flex h-full flex-col gap-4 p-5" data-testid={`connect-org-${org.login}`}>
                      <span className="workspace-card-top"><span className="workspace-eyebrow">{String(i + 1).padStart(2, '0')} / ORGANIZATION</span><svg className="workspace-arrow" aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M6 18 18 6M6 6h12v12" stroke="currentColor" strokeWidth="1.5" /></svg></span>
                      <span className="flex items-center gap-3">
                        <Avatar login={org.login} size={40} />
                        <span className="min-w-0 truncate font-semibold">{org.login}</span>
                      </span>
                      <span className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
                        <span>{org.repos.length} {org.repos.length === 1 ? 'repository' : 'repositories'}</span>
                        {org.connected > 0 && <span className="text-ok">{org.connected} connected</span>}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
            {orgs.length > 0 && install && (
              <p className="mt-6 text-sm text-muted">Missing an organization or repository? <a className="text-brand underline-offset-2 hover:underline" href={install}>Add it to the GitHub App</a>.</p>
            )}
          </>
        );
      })()}
    </div>
  );
}
