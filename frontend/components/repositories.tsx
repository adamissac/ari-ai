'use client';

import type { Repository, Snapshot } from '@hackatl/frontend-transport';
import Link from 'next/link';
import { useEffect, useState, type FormEvent } from 'react';
import { useProject } from '@/components/project';
import { Badge, Button, Empty, ErrorState, Field, inputClass, Mono, Panel } from '@/components/ui';
import { api, idempotencyKey } from '@/lib/api';
import { CONNECT_REPOSITORY_NOTE } from '@/lib/connect';
import { INDEX_COMMIT_NOTE } from '@/lib/index-commit';
import { shortSha } from '@/lib/format';
import { SNAPSHOT_STATUS } from '@/lib/status';
import { RepoCommits } from '@/components/repo-commits';
import { RepoPicker } from '@/components/repo-picker';

const SHA = /^[0-9a-f]{7,40}$/;
// The API refuses name-only connections outside development/test, so only dev builds offer the form.
const NAME_ONLY_CONNECT = process.env.NEXT_PUBLIC_DEV_LOGIN === '1';

export function Repositories({ repos }: { repos: Repository[] }) {
  const { project, reloadRepos } = useProject();
  const [fullName, setFullName] = useState('');
  const [branch, setBranch] = useState('main');
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const connect = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api().connectRepository(project.id, { full_name: fullName.trim(), default_branch: branch.trim() || 'main', installation_id: null });
      setFullName('');
      reloadRepos();
    } catch (err) { setError(err); } finally { setBusy(false); }
  };
  return (
    <Panel title="Repositories" id="connect-repo" actions={<Link className="text-xs text-brand hover:text-ink" href="/connect">Connect another repository →</Link>}>
      {repos.length === 0 ? <Empty>No repository connected.</Empty> : (
        <>
          <p className="mb-3 text-sm text-muted" data-testid="index-commit-note">{INDEX_COMMIT_NOTE}</p>
          <ul className="divide-y divide-line">
            {repos.map(repo => <RepoRow key={repo.id} repo={repo} />)}
          </ul>
        </>
      )}
      <div className="mt-4 border-t border-line pt-3"><RepoPicker projectId={project.id} onConnected={reloadRepos} /></div>
      {NAME_ONLY_CONNECT && <>
        <p className="label-mono mt-4 text-faint">Or by name (development only: an operator provides the checkout)</p>
        <p className="mt-1 text-sm text-muted" data-testid="connect-repository-note">{CONNECT_REPOSITORY_NOTE}</p>
        <form onSubmit={connect} className="mt-2 grid gap-2 sm:grid-cols-[2fr_1fr_auto] sm:items-end">
          <Field label="owner/name"><input className={inputClass} value={fullName} onChange={event => setFullName(event.target.value)} required pattern="[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+" name="full_name" /></Field>
          <Field label="Default branch"><input className={inputClass} value={branch} onChange={event => setBranch(event.target.value)} name="default_branch" /></Field>
          <Button type="submit" disabled={busy || !fullName.trim()}>Connect</Button>
        </form>
      </>}
      {error !== null && <div className="mt-2"><ErrorState error={error} context="Connect failed" /></div>}
    </Panel>
  );
}

function RepoRow({ repo }: { repo: Repository }) {
  if (repo.disconnected) return <DisconnectedRow repo={repo} />;
  return <ConnectedRow repo={repo} />;
}

/** A disconnected repository keeps its history but Ari reads nothing until it is reconnected. */
function DisconnectedRow({ repo }: { repo: Repository }) {
  const { reloadRepos } = useProject();
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const reconnect = async () => {
    setBusy(true);
    setError(null);
    try { await api().reconnectRepository(repo.id); reloadRepos(); } catch (err) { setError(err); } finally { setBusy(false); }
  };
  return (
    <li className="py-4 first:pt-0 last:pb-0" data-testid={`repo-disconnected-${repo.full_name}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-medium">{repo.full_name} <span className="text-xs font-normal text-warn">· Disconnected</span></span>
        <Button disabled={busy} onClick={() => void reconnect()}>{busy ? 'Reconnecting…' : 'Reconnect'}</Button>
      </div>
      <p className="mt-2 text-xs text-muted">Ari stopped reading this repository. Past reviews stay visible. Reconnecting re-checks your GitHub access; automatic reviews stay off until you turn them on.</p>
      {error !== null && <div className="mt-2"><ErrorState error={error} context="Reconnect failed" /></div>}
    </li>
  );
}

function ConnectedRow({ repo }: { repo: Repository }) {
  const { reloadRepos } = useProject();
  const [reattach, setReattach] = useState<{ busy: boolean; error: unknown }>({ busy: false, error: null });
  // An uninstall detaches the grant but keeps the row live; reconnect re-verifies and records a new one.
  const reattachApp = async () => {
    setReattach({ busy: true, error: null });
    try { await api().reconnectRepository(repo.id); reloadRepos(); setReattach({ busy: false, error: null }); }
    catch (err) { setReattach({ busy: false, error: err }); }
  };
  const [sha, setSha] = useState('');
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!snapshot || snapshot.status === 'ready' || snapshot.status === 'failed') return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      api().snapshot(snapshot.id, { signal: controller.signal }).then(setSnapshot, (err: unknown) => {
        if (!controller.signal.aborted) setError(err);
      });
    }, 2000);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [snapshot]);

  const index = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try { setSnapshot(await api().createSnapshot(repo.id, { commit_sha: sha.trim() }, idempotencyKey('snapshot'))); }
    catch (err) { setError(err); } finally { setBusy(false); }
  };

  return (
    <li className="py-4 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-medium">{repo.full_name}</span>
        <span className="flex flex-wrap items-center gap-3 text-xs text-muted">
          {repo.default_branch} · {repo.installation_id ? 'GitHub App installed' : 'no GitHub App installation'}
          {!repo.installation_id && !NAME_ONLY_CONNECT && <Button disabled={reattach.busy} onClick={() => void reattachApp()}>{reattach.busy ? 'Checking GitHub…' : 'Reattach GitHub App'}</Button>}
          <Link className="text-brand hover:underline" href={`/projects/${repo.project_id}/simulate?repo=${encodeURIComponent(repo.id)}`} data-testid={`simulate-${repo.full_name}`}>Attack walkthrough →</Link>
        </span>
      </div>
      <div className="mt-3"><RepoCommits repo={repo} onPick={setSha} /></div>
      <form onSubmit={index} className="mt-2 flex flex-wrap items-center gap-2">
        <input aria-label={`Commit to index for ${repo.full_name}`} className={`${inputClass} flex-1 font-mono`} value={sha} onChange={event => setSha(event.target.value.toLowerCase())} pattern="[0-9a-f]{7,40}" placeholder="commit sha to index" required />
        <Button type="submit" disabled={busy || !SHA.test(sha)}>Index commit</Button>
      </form>
      {snapshot && (
        <p className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted">
          <Badge view={SNAPSHOT_STATUS[snapshot.status]} /> <Mono>{snapshot.id}</Mono> at <Mono>{shortSha(snapshot.commit_sha)}</Mono>
          {snapshot.status === 'ready' && <> · {snapshot.stats.files} files · {snapshot.stats.symbols} symbols · {snapshot.stats.call_edges} call edges · {snapshot.stats.entry_points} entry points · {snapshot.stats.expectations} expectations</>}
          {snapshot.error_message && <span className="text-bad">{snapshot.error_message}</span>}
        </p>
      )}
      {reattach.error !== null && <div className="mt-2"><ErrorState error={reattach.error} context="Reattach failed" /></div>}
      {error !== null && <div className="mt-2"><ErrorState error={error} context="Snapshot" /></div>}
    </li>
  );
}
