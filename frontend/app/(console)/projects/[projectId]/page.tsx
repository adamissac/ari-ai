'use client';

import type { Assessment, Repository, Snapshot } from '@hackatl/frontend-transport';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState, type FormEvent } from 'react';
import { useProject } from '@/components/project';
import { Async, Badge, Button, Empty, ErrorState, Field, inputClass, Mono, Panel, Stat, Time } from '@/components/ui';
import { api, idempotencyKey } from '@/lib/api';
import { shortSha, usd } from '@/lib/format';
import { ASSESSMENT_STATE, FINDING_STATUS, SNAPSHOT_STATUS } from '@/lib/status';
import { useResource } from '@/lib/use-resource';

const SHA = /^[0-9a-f]{7,40}$/;

export default function ProjectOverview() {
  const { project, repos } = useProject();
  const assessments = useResource(`asm:${project.id}`, s => api().assessments(project.id, { signal: s }), 5000);
  const findings = useResource(`fnd:${project.id}`, s => api().findings(project.id, { signal: s }), 10000);
  return (
    <div className="grid gap-4 lg:grid-cols-[3fr_2fr]">
      <div className="flex flex-col gap-4">
        <Panel title="Assessments" actions={<span className="text-xs text-muted">refreshes every 5 s</span>}>
          <Async resource={assessments} label="assessments">
            {page => <AssessmentList projectId={project.id} items={page.items} />}
          </Async>
        </Panel>
        <StartAssessment onStarted={assessments.reload} />
      </div>
      <div className="flex flex-col gap-4">
        <Panel title="Findings">
          <Async resource={findings} label="findings">
            {page => {
              const verified = page.items.filter(f => f.status === 'verified' || f.status === 'hardened').length;
              const hypotheses = page.items.filter(f => f.status === 'hypothesis').length;
              return (
                <>
                  <div className="grid grid-cols-3 gap-2">
                    <Stat label="Total" value={page.items.length} />
                    <Stat label="Hypotheses" value={hypotheses} hint="unvalidated" />
                    <Stat label="Verified fixes" value={verified} />
                  </div>
                  <ul className="mt-3 divide-y divide-line">
                    {page.items.slice(0, 6).map(f => (
                      <li key={f.id} className="flex items-center justify-between gap-2 py-2 text-sm">
                        <Link className="truncate hover:text-accent" href={`/projects/${project.id}/findings/${f.id}`}>{f.title}</Link>
                        <Badge view={FINDING_STATUS[f.status]} />
                      </li>
                    ))}
                  </ul>
                  {page.items.length === 0 && <Empty>No findings recorded for this project.</Empty>}
                </>
              );
            }}
          </Async>
        </Panel>
        <Repositories repos={repos} />
      </div>
    </div>
  );
}

function AssessmentList({ projectId, items }: { projectId: string; items: Assessment[] }) {
  if (items.length === 0) return <Empty>No assessments yet. Approve a scope, then start one below.</Empty>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="text-xs uppercase tracking-wider text-faint">
          <tr><th className="py-1.5 pr-3">Assessment</th><th className="pr-3">State</th><th className="pr-3">Commit</th><th className="pr-3">Trigger</th><th className="pr-3">Usage</th><th>Created</th></tr>
        </thead>
        <tbody className="divide-y divide-line">
          {items.map(a => (
            <tr key={a.id}>
              <td className="py-2 pr-3"><Link className="font-mono text-xs text-accent hover:underline" href={`/projects/${projectId}/assessments/${a.id}`}>{a.id}</Link></td>
              <td className="pr-3"><Badge view={ASSESSMENT_STATE[a.state]} /></td>
              <td className="pr-3"><Mono>{shortSha(a.commit_sha)}</Mono></td>
              <td className="pr-3 text-muted">{a.trigger}</td>
              <td className="pr-3 text-muted">{a.usage.llm_calls} calls · {usd(a.usage.usd)}</td>
              <td className="text-muted"><Time iso={a.created_at} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StartAssessment({ onStarted }: { onStarted: () => void }) {
  const { project, repos } = useProject();
  const router = useRouter();
  const scopes = useResource(`scopes:${project.id}`, s => api().scopes(project.id, { signal: s }));
  const [repoId, setRepoId] = useState('');
  const [scopeId, setScopeId] = useState('');
  const [sha, setSha] = useState('');
  // An unchanged retry of the same action reuses its key; any edit is a new action.
  const [key, setKey] = useState<{ sig: string; value: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const active = scopes.status === 'ready' ? scopes.data.items.filter(s => s.status === 'active') : [];

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const sig = `${repoId}|${scopeId}|${sha.trim()}`;
    const actionKey = key?.sig === sig ? key.value : idempotencyKey('assessment');
    setKey({ sig, value: actionKey });
    setBusy(true);
    setError(null);
    try {
      const asm = await api().startAssessment(project.id, { scope_id: scopeId, repo_id: repoId, commit_sha: sha.trim() || null, snapshot_id: null, budget: null }, actionKey);
      onStarted();
      router.push(`/projects/${project.id}/assessments/${asm.id}`);
    } catch (err) { setError(err); } finally { setBusy(false); }
  };

  return (
    <Panel title="Start an assessment">
      {repos.length === 0 ? <Empty>Connect a repository first.</Empty> : (
        <form onSubmit={submit} className="grid gap-3 sm:grid-cols-3">
          <Field label="Repository">
            <select className={inputClass} value={repoId} onChange={e => setRepoId(e.target.value)} required name="repo">
              <option value="">Select…</option>
              {repos.map(r => <option key={r.id} value={r.id}>{r.full_name}</option>)}
            </select>
          </Field>
          <Field label="Authorized scope" hint={scopes.status === 'ready' && active.length === 0 ? 'No active scope — request and approve one under Scopes.' : undefined}>
            <select className={inputClass} value={scopeId} onChange={e => setScopeId(e.target.value)} required name="scope">
              <option value="">Select…</option>
              {active.filter(s => !repoId || s.targets.some(t => t.repo_id === repoId)).map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </Field>
          <Field label="Commit SHA" hint="Blank = backend default for the repository.">
            <input className={`${inputClass} font-mono`} value={sha} onChange={e => setSha(e.target.value.toLowerCase())} pattern="[0-9a-f]{7,40}" name="commit_sha" placeholder="optional" />
          </Field>
          <div className="sm:col-span-3 flex flex-wrap items-center gap-3">
            <Button type="submit" variant="primary" disabled={busy || !repoId || !scopeId || (sha !== '' && !SHA.test(sha))}>Start assessment</Button>
            <span className="text-xs text-muted">Runs only against the targets in the selected, human-approved scope.</span>
          </div>
          {error !== null && <div className="sm:col-span-3"><ErrorState error={error} context="Assessment not started" /></div>}
        </form>
      )}
    </Panel>
  );
}

function Repositories({ repos }: { repos: Repository[] }) {
  const { project, reloadRepos } = useProject();
  const [fullName, setFullName] = useState('');
  const [branch, setBranch] = useState('main');
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const connect = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api().connectRepository(project.id, { full_name: fullName.trim(), default_branch: branch.trim() || 'main', installation_id: null });
      setFullName('');
      reloadRepos();
    } catch (err) { setError(err); } finally { setBusy(false); }
  };
  return (
    <Panel title="Repositories">
      {repos.length === 0 ? <Empty>No repository connected.</Empty> : (
        <ul className="flex flex-col gap-3">
          {repos.map(r => <RepoRow key={r.id} repo={r} />)}
        </ul>
      )}
      <form onSubmit={connect} className="mt-4 grid gap-2 border-t border-line pt-3 sm:grid-cols-[2fr_1fr_auto] sm:items-end">
        <Field label="owner/name"><input className={inputClass} value={fullName} onChange={e => setFullName(e.target.value)} required pattern="[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+" name="full_name" /></Field>
        <Field label="Default branch"><input className={inputClass} value={branch} onChange={e => setBranch(e.target.value)} name="default_branch" /></Field>
        <Button type="submit" disabled={busy || !fullName.trim()}>Connect</Button>
      </form>
      {error !== null && <div className="mt-2"><ErrorState error={error} context="Connect failed" /></div>}
    </Panel>
  );
}

function RepoRow({ repo }: { repo: Repository }) {
  const [sha, setSha] = useState('');
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  // Poll the requested snapshot until the indexer reports a terminal status.
  useEffect(() => {
    if (!snapshot || snapshot.status === 'ready' || snapshot.status === 'failed') return;
    const controller = new AbortController();
    const t = setTimeout(() => {
      api().snapshot(snapshot.id, { signal: controller.signal }).then(setSnapshot, (err: unknown) => { if (!controller.signal.aborted) setError(err); });
    }, 2000);
    return () => { clearTimeout(t); controller.abort(); };
  }, [snapshot]);

  const index = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try { setSnapshot(await api().createSnapshot(repo.id, { commit_sha: sha.trim() }, idempotencyKey('snapshot'))); }
    catch (err) { setError(err); } finally { setBusy(false); }
  };

  return (
    <li className="rounded-md border border-line bg-panel-2 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-medium">{repo.full_name}</span>
        <span className="text-xs text-muted">{repo.default_branch} · {repo.installation_id ? 'GitHub App installed' : 'no GitHub App installation'}</span>
      </div>
      <form onSubmit={index} className="mt-2 flex flex-wrap items-center gap-2">
        <input aria-label={`Commit to index for ${repo.full_name}`} className={`${inputClass} flex-1 font-mono`} value={sha} onChange={e => setSha(e.target.value.toLowerCase())} pattern="[0-9a-f]{7,40}" placeholder="commit sha to index" required />
        <Button type="submit" disabled={busy || !SHA.test(sha)}>Index commit</Button>
      </form>
      {snapshot && (
        <p className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted">
          <Badge view={SNAPSHOT_STATUS[snapshot.status]} /> <Mono>{snapshot.id}</Mono> at <Mono>{shortSha(snapshot.commit_sha)}</Mono>
          {snapshot.status === 'ready' && <> · {snapshot.stats.files} files · {snapshot.stats.symbols} symbols · {snapshot.stats.call_edges} call edges · {snapshot.stats.entry_points} entry points · {snapshot.stats.expectations} expectations</>}
          {snapshot.error_message && <span className="text-bad">{snapshot.error_message}</span>}
        </p>
      )}
      {error !== null && <div className="mt-2"><ErrorState error={error} context="Snapshot" /></div>}
    </li>
  );
}

