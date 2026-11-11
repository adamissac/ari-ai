'use client';

import Link from 'next/link';
import { Avatar, GitHubMark } from '@/components/demo/ui';
import { BRAND_NAME } from '@/components/brand';
import { Details, ErrorState, Loading, PageTitle, Panel } from '@/components/ui';
import { RefreshFromGitHub } from '@/components/refresh-from-github';
import { SetupLayout } from '@/components/onboarding/stepper';
import { api } from '@/lib/api';
import { groupByOrg } from '@/lib/github-orgs';
import { useResource } from '@/lib/use-resource';

/** After GitHub sign-in: choose the organization (App installation account) to work in. */
export default function ConnectOrgsPage() {
  const list = useResource('github-repos', signal => api().githubRepositories({ signal }));

  return (
    <SetupLayout current={1}>
      <div className="min-w-0" data-testid="connect-orgs">
        <PageTitle title="Organizations" subtitle="Choose an organization to see its repositories" actions={<RefreshFromGitHub />} />
        <section aria-label="GitHub App permissions" className="mb-6 flex flex-wrap items-center gap-2 text-xs text-muted">
          <span className="label-mono text-faint">GitHub App</span>
          {['Contents: read & write', 'Pull requests: read & write', 'Metadata: read-only', 'Events: push, pull request, repository'].map(p => <span key={p} className="rounded-md border border-line bg-panel px-2 py-1 text-ink">{p}</span>)}
          <span className="basis-full sm:basis-auto"><strong className="font-medium text-ink">Revoke or limit access</strong> in GitHub → Settings → Installed GitHub Apps → Ari</span>
        </section>
        {list.status === 'loading' && <Loading label="Loading your GitHub organizations" />}
        {list.status === 'error' && <ErrorState error={list.error} onRetry={list.reload} context="Could not list your GitHub repositories" />}
        {list.status === 'ready' && (() => {
          const orgs = groupByOrg(list.data.items);
          const install = list.data.install_url;
          return (
            <>
              {orgs.length === 0 ? (
                <Panel title="No repositories yet" className="text-center">
                  <p data-testid="connect-empty" className="mx-auto max-w-md text-sm text-muted">Install the {BRAND_NAME} GitHub App on an organization or your account.</p>
                  {install === null && <p className="mx-auto mt-3 max-w-md text-sm text-muted" data-testid="connect-no-install-link">If the App is already installed, use Refresh from GitHub above. Otherwise ask an owner of your GitHub organization to install it, then refresh.</p>}
                  {install !== null && <a href={install} className="mt-5 inline-flex h-9 items-center gap-2 rounded-lg bg-brand px-3.5 text-sm font-medium text-on-brand hover:bg-brand-deep"><GitHubMark />Install the GitHub App</a>}
                </Panel>
              ) : (
                <ul className="grid grid-cols-[repeat(auto-fill,minmax(18rem,1fr))] gap-3">
                  {orgs.map((org, i) => (
                    <li key={org.login}>
                      <Link href={`/connect/${encodeURIComponent(org.login)}`} className="group flex h-full min-w-0 flex-col gap-4 rounded-2xl border border-line bg-panel p-5 transition-colors hover:bg-panel-2" data-testid={`connect-org-${org.login}`}>
                        <span className="flex w-full items-center justify-between gap-4"><span className="label-mono text-muted">Organization {i + 1}</span><span aria-hidden="true" className="text-2xl text-muted transition-transform group-hover:translate-x-1">↗</span></span>
                        <span className="flex items-center gap-3">
                          <Avatar login={org.login} size={40} />
                          <span className="min-w-0 truncate font-semibold">{org.login}</span>
                        </span>
                        <span className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
                          <span>{org.repos.length} {org.repos.length === 1 ? 'repository' : 'repositories'}</span>
                          {org.connected > 0 && <span className="text-info">{org.connected} connected</span>}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
              {orgs.length > 0 && install !== null && (
                <p className="mt-6 text-sm text-muted">Missing an organization or repository? <a className="text-brand underline-offset-2 hover:underline" href={install}>Add it to the GitHub App</a>.</p>
              )}
            </>
          );
        })()}
        <div className="mt-4">
          <Details summary="Permissions and what happens next">
            <ul className="flex flex-col gap-1">
              <li><strong className="font-medium text-ink">Contents</strong>: read code to review; write only to open the build-recipe PR and fix PRs you approve.</li>
              <li><strong className="font-medium text-ink">Pull requests</strong>: open those PRs and leave review comments if you turn comments on.</li>
              <li><strong className="font-medium text-ink">Events</strong>: used only for reviews you enable; automatic reviews are off by default.</li>
            </ul>
            <section aria-label="What happens next" data-testid="connect-next-steps">
              <h2 className="label-mono mb-2 text-muted">What happens when you connect a repository</h2>
              <ol className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-3">
                <li className="rounded-lg border border-line p-3"><p className="font-medium text-ink">1 · No check runs yet</p><p className="mt-1 text-muted">Connecting records the repository. If it has no build recipe, Ari proposes one as a pull request on <code className="font-mono text-xs">ari/build-recipe</code> for you to merge or close. No tests run and nothing is pushed to your default branch.</p></li>
                <li className="rounded-lg border border-line p-3"><p className="font-medium text-ink">2 · You answer eight setup questions</p><p className="mt-1 text-muted">Including whether to approve sandbox testing for 30 days and how verified fixes reach you. Automatic reviews stay off unless you turn them on.</p></li>
                <li className="rounded-lg border border-line p-3"><p className="font-medium text-ink">3 · You start the first check</p><p className="mt-1 text-muted">The agents review one commit in an isolated copy and record findings with evidence. You approve any fix before it is built.</p></li>
              </ol>
            </section>
          </Details>
        </div>
      </div>
    </SetupLayout>
  );
}
