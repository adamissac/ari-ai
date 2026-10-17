'use client';

import type { AccessibleRepository } from '@hackatl/frontend-transport';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useState } from 'react';
import { Avatar } from '@/components/demo/ui';
import { Button, ErrorState, Loading, Tag } from '@/components/ui';
import { api, idempotencyKey } from '@/lib/api';
import { groupByOrg, repoName } from '@/lib/github-orgs';
import { useResource } from '@/lib/use-resource';

/** One project per organization: found by name, created on the first connect. */
async function projectFor(org: string): Promise<string> {
  const existing = (await api().projects()).items.find(p => p.name === org);
  if (existing) return existing.id;
  return (await api().createProject({ name: org, org_id: null, settings: null }, { idempotencyKey: idempotencyKey('project') })).id;
}

/** Second step: choose a repository in the organization and connect it. */
export default function ConnectReposPage() {
  const { org: raw } = useParams<{ org: string }>();
  const login = decodeURIComponent(raw);
  const router = useRouter();
  const list = useResource('github-repos', signal => api().githubRepositories({ signal }));
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  const open = async (repo: AccessibleRepository) => {
    setBusy(repo.full_name);
    setError(null);
    try {
      const pid = await projectFor(login);
      if (!repo.connected_repo_id) {
        await api().connectRepository(pid, { full_name: repo.full_name, default_branch: repo.default_branch, installation_id: repo.installation_id });
      }
      router.push(`/projects/${pid}`);
    } catch (err) { setError(err); setBusy(null); }
  };

  const org = list.status === 'ready' ? groupByOrg(list.data.items).find(o => o.login === login) : undefined;

  return (
    <div className="mx-auto max-w-5xl px-4 py-8" data-testid="connect-repos">
      <nav aria-label="Breadcrumb" className="mb-5 text-sm text-muted">
        <Link href="/connect" className="hover:text-ink">Organizations</Link><span aria-hidden="true" className="mx-2">/</span><span className="text-ink">{login}</span>
      </nav>
      <header className="mb-6 flex flex-wrap items-center gap-4">
        <Avatar login={login} size={48} />
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">{login}</h1>
          <p className="mt-1 text-sm text-muted">Choose a repository. Ari AI reads it through the GitHub App with read-only access; push events are checked once the App webhook is delivering.</p>
        </div>
      </header>
      {list.status === 'loading' && <Loading label="Loading repositories" />}
      {list.status === 'error' && <ErrorState error={list.error} onRetry={list.reload} context="Could not list your GitHub repositories" />}
      {list.status === 'ready' && !org && (
        <p className="text-sm text-muted" data-testid="connect-org-missing">No repositories from {login} are available to you. <Link className="text-brand hover:underline" href="/connect">Choose another organization</Link>.</p>
      )}
      {org && (
        <ul className="flex flex-col divide-y divide-line overflow-hidden rounded-2xl border border-line bg-panel">
          {org.repos.map(repo => (
            <li key={repo.full_name} className="flex flex-wrap items-center justify-between gap-3 px-5 py-4" data-testid={`connect-repo-${repo.full_name}`}>
              <span className="flex min-w-0 flex-wrap items-center gap-2">
                <span className="truncate font-semibold">{repoName(repo.full_name)}</span>
                {repo.private && <Tag>private</Tag>}
                <span className="font-mono text-xs text-faint">{repo.default_branch}</span>
                {repo.connected_repo_id && <span className="text-xs text-ok">Connected</span>}
              </span>
              <Button variant={repo.connected_repo_id ? 'secondary' : 'primary'} aria-label={`${repo.connected_repo_id ? 'Open' : 'Connect'} ${repo.full_name}`} disabled={busy !== null} onClick={() => void open(repo)}>
                {busy === repo.full_name ? 'Opening…' : repo.connected_repo_id ? 'Open' : 'Connect'}
              </Button>
            </li>
          ))}
        </ul>
      )}
      {error !== null && <div className="mt-3"><ErrorState error={error} context="Could not connect the repository" /></div>}
    </div>
  );
}
