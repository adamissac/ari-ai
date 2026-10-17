'use client';

import type { AccessibleRepository } from '@hackatl/frontend-transport';
import { useState } from 'react';
import { Button, ErrorState, Loading, Mono, Tag } from '@/components/ui';
import { api } from '@/lib/api';
import { useResource } from '@/lib/use-resource';

/**
 * Repositories the signed-in user can connect through the Ari AI GitHub App. The backend
 * captured this list at GitHub sign-in and only accepts a connection that matches it.
 */
export function RepoPicker({ projectId, onConnected }: { projectId: string; onConnected: () => void }) {
  const list = useResource('github-repos', signal => api().githubRepositories({ signal }));
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  const connect = async (repo: AccessibleRepository) => {
    setBusy(repo.full_name);
    setError(null);
    try {
      await api().connectRepository(projectId, { full_name: repo.full_name, default_branch: repo.default_branch, installation_id: repo.installation_id });
      list.reload();
      onConnected();
    } catch (err) { setError(err); } finally { setBusy(null); }
  };

  if (list.status === 'loading') return <Loading label="Loading your GitHub repositories" />;
  if (list.status === 'error') return <ErrorState error={list.error} onRetry={list.reload} context="Could not list your GitHub repositories" />;
  const { items, install_url } = list.data;
  return (
    <section aria-label="Your GitHub repositories" data-testid="repo-picker">
      <p className="label-mono text-faint">From GitHub</p>
      {items.length === 0 ? (
        <p className="mt-2 text-sm text-muted" data-testid="repo-picker-empty">
          No repositories yet. {install_url
            ? <>Install the <a className="text-brand underline-offset-2 hover:underline" href={install_url}>Ari AI GitHub App</a> on the repositories you want checked; GitHub then signs you in again and they appear here.</>
            : <>Install the Ari AI GitHub App on the repositories you want checked, then sign in with GitHub again.</>}
        </p>
      ) : (
        <ul className="mt-2 flex flex-col divide-y divide-line rounded-xl border border-line">
          {items.map(repo => (
            <li key={repo.full_name} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
              <span className="flex min-w-0 flex-wrap items-center gap-2">
                <Mono className="truncate">{repo.full_name}</Mono>
                {repo.private && <Tag>private</Tag>}
                <span className="text-xs text-faint">{repo.default_branch}</span>
              </span>
              {repo.connected_repo_id
                ? <span className="text-xs text-ok">Connected</span>
                : <Button variant="primary" aria-label={`Connect ${repo.full_name}`} disabled={busy !== null} onClick={() => void connect(repo)}>{busy === repo.full_name ? 'Connecting…' : 'Connect'}</Button>}
            </li>
          ))}
        </ul>
      )}
      {error !== null && <div className="mt-2"><ErrorState error={error} context="Connect failed" /></div>}
    </section>
  );
}
