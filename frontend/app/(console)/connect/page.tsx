'use client';

import Link from 'next/link';
import { Avatar, GitHubMark } from '@/components/demo/ui';
import { BRAND_NAME } from '@/components/brand';
import { ErrorState, Loading } from '@/components/ui';
import { useSession } from '@/components/session';
import { api } from '@/lib/api';
import { groupByOrg } from '@/lib/github-orgs';
import { useResource } from '@/lib/use-resource';

/** After GitHub sign-in: choose the organization (App installation account) to work in. */
export default function ConnectOrgsPage() {
  const { me } = useSession();
  const list = useResource('github-repos', signal => api().githubRepositories({ signal }));

  return (
    <div className="mx-auto max-w-5xl px-4 py-8" data-testid="connect-orgs">
      <header className="mb-6">
        <p className="label-mono text-brand">Signed in as {me.user.github_login}</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Where should {BRAND_NAME} look?</h1>
        <p className="mt-1.5 text-sm text-muted">Pick an organization. Only repositories the {BRAND_NAME} GitHub App is installed on appear here.</p>
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
                <p className="mx-auto mt-1.5 max-w-md text-sm text-muted">Install the {BRAND_NAME} GitHub App on an organization or on your account and choose the repositories to check. GitHub brings you straight back here.</p>
                {install && <a href={install} className="mt-5 inline-flex h-10 items-center gap-2 rounded-lg bg-[#1c1210] px-4 text-sm font-medium text-white hover:bg-brand"><GitHubMark />Install the GitHub App</a>}
              </div>
            ) : (
              <ul className="grid gap-3 md:grid-cols-3">
                {orgs.map((org, i) => (
                  <li key={org.login} className="demo-rise" style={{ ['--i' as string]: i }}>
                    <Link href={`/connect/${encodeURIComponent(org.login)}`} className="demo-card group flex h-full flex-col gap-4 p-5" data-testid={`connect-org-${org.login}`}>
                      <span className="flex items-center gap-3">
                        <Avatar login={org.login} size={40} />
                        <span className="min-w-0">
                          <span className="block truncate font-semibold">{org.login}</span>
                          <span className="block truncate font-mono text-xs text-muted">github.com/{org.login}</span>
                        </span>
                      </span>
                      <span className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
                        <span>{org.repos.length} {org.repos.length === 1 ? 'repository' : 'repositories'}</span>
                        {org.private > 0 && <span>{org.private} private</span>}
                        {org.connected > 0 && <span className="text-ok">{org.connected} connected</span>}
                      </span>
                      <span className="mt-auto text-sm font-medium text-brand">Open <span aria-hidden="true" className="inline-block transition-transform group-hover:translate-x-1">→</span></span>
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
