'use client';

import type { DeliveryMode, Repository } from '@hackatl/frontend-transport';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useState, type ReactNode } from 'react';
import { BackdropShapes } from '@/components/backdrop-shapes';
import { useProject } from '@/components/project';
import { RepositoryAutomation } from '@/components/repository-automation';
import { Button, ErrorState, Loading } from '@/components/ui';
import { api } from '@/lib/api';
import { useActionKeys } from '@/lib/action-key';
import { scopeBody, scopeStateFor } from '@/lib/real-assessment';
import { useResource } from '@/lib/use-resource';

const STRICTNESS: Array<[number, string, string]> = [
  [1, 'Thorough', 'Comment on every finding, including low severity.'],
  [2, 'Balanced', 'Comment on medium severity and above. Recommended.'],
  [3, 'Critical only', 'Comment only on high and critical findings.'],
];
const DELIVERY: Array<[DeliveryMode, string, string]> = [
  ['pull_request', 'Open a pull request', 'Each verified fix arrives as a PR. You review and merge. Recommended.'],
  ['manual', 'Ask me first', 'Nothing is pushed until you approve each fix in Ari.'],
  ['auto', 'Commit to the default branch', 'Ari pushes verified fixes straight to your default branch with no human check.'],
];

type StepState = 'done' | 'current' | 'upcoming';

/** Guided setup after connecting a repository: authorize, tune the reviewer, choose delivery, run. */
export default function SetupPage() {
  const { project, reloadProject } = useProject();
  const repoParam = useSearchParams().get('repo');
  const repos = useResource(`setup-repos:${project.id}`, signal => api().repositories(project.id, { signal }));
  const scopes = useResource(`setup-scopes:${project.id}`, signal => api().scopes(project.id, { signal }));
  const runs = useResource(`setup-runs:${project.id}`, signal => api().assessments(project.id, { signal }));

  if (repos.status === 'loading' || scopes.status === 'loading' || runs.status === 'loading') return <Loading label="Loading setup" />;
  if (repos.status === 'error') return <ErrorState error={repos.error} onRetry={repos.reload} />;
  if (scopes.status === 'error') return <ErrorState error={scopes.error} onRetry={scopes.reload} />;
  if (runs.status === 'error') return <ErrorState error={runs.error} onRetry={runs.reload} />;
  const repo = repos.data.items.find(r => r.id === repoParam) ?? repos.data.items[0];
  if (!repo) {
    return <div className="rounded-2xl border border-line bg-panel p-6 text-sm">No repository is connected yet. <Link className="font-semibold text-brand" href="/connect">Connect one</Link> to start setup.</div>;
  }
  const scope = scopeStateFor(scopes.data.items, repo.id, new Date());
  const authorized = scope.kind === 'active';
  const hasRun = runs.data.items.some(a => a.repo_id === repo.id);
  return (
    <Walkthrough
      key={repo.id}
      repo={repo}
      scope={scope}
      authorized={authorized}
      hasRun={hasRun}
      reload={() => { scopes.reload(); runs.reload(); reloadProject(); }}
    />
  );
}

function Walkthrough({ repo, scope, authorized, hasRun, reload }: {
  repo: Repository; scope: ReturnType<typeof scopeStateFor>; authorized: boolean; hasRun: boolean; reload: () => void;
}) {
  const { project, reloadProject } = useProject();
  const router = useRouter();
  const scopeKeys = useActionKeys('setup-scope');
  const runKeys = useActionKeys('setup-run');
  const review = project.settings.review;
  const [strictness, setStrictness] = useState(review.strictness);
  const [pushes, setPushes] = useState(review.review_pushes);
  const [prs, setPrs] = useState(review.review_pull_requests);
  const [comments, setComments] = useState(review.comment_on_pull_requests);
  const [monitoring, setMonitoring] = useState(project.settings.monitoring_policy.enabled);
  const [delivery, setDelivery] = useState<DeliveryMode>(project.settings.delivery_mode === 'auto' ? 'pull_request' : project.settings.delivery_mode);
  const progressKey = `ari-setup:${project.id}:${repo.id}`;
  // Walkthrough mounts only after client-side data loads, so localStorage is available here.
  const savedSteps = (): string => (typeof window === 'undefined' ? '' : window.localStorage.getItem(progressKey) ?? '');
  const [reviewerSaved, setReviewerSaved] = useState(() => savedSteps().includes('reviewer'));
  const [deliverySaved, setDeliverySaved] = useState(() => savedSteps().includes('delivery'));
  const markSaved = (step: 'reviewer' | 'delivery') => {
    const saved = savedSteps();
    if (!saved.includes(step)) window.localStorage.setItem(progressKey, `${saved} ${step}`.trim());
  };
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  const act = async (label: string, fn: () => Promise<void>) => {
    setBusy(label); setError(null);
    try { await fn(); } catch (err) { setError(err); } finally { setBusy(null); }
  };
  const save = (settings: typeof project.settings) => api().updateProject(project.id, { name: project.name, settings }).then(() => reloadProject());

  const requestScope = () => act('scope', async () => {
    const sig = `${project.id}|${repo.id}`;
    const body = scopeKeys.payloadFor(sig, () => scopeBody(repo.id, new Date()));
    const created = await api().createScope(project.id, body, { idempotencyKey: scopeKeys.keyFor(sig) });
    scopeKeys.done();
    await api().approveScope(created.id);
    reload();
  });
  const approveScope = (id: string) => act('scope', async () => { await api().approveScope(id); reload(); });
  const saveReviewer = () => act('reviewer', async () => {
    await save({
      ...project.settings,
      monitoring_policy: { ...project.settings.monitoring_policy, enabled: monitoring },
      review: { ...review, strictness, review_pushes: pushes, review_pull_requests: prs, comment_on_pull_requests: comments },
    });
    setReviewerSaved(true);
    markSaved('reviewer');
  });
  const saveDelivery = () => act('delivery', async () => {
    if (delivery === 'auto' && !window.confirm('Ari will commit verified fixes straight to your default branch with no human check. Continue?')) return;
    await save({ ...project.settings, delivery_mode: delivery });
    setDeliverySaved(true);
    markSaved('delivery');
  });
  const run = () => act('run', async () => {
    if (scope.kind !== 'active') return;
    const sig = `${project.id}|${repo.id}`;
    const asm = await api().startAssessment(project.id, { scope_id: scope.scope.id, repo_id: repo.id, commit_sha: null, snapshot_id: null, budget: null }, runKeys.keyFor(sig));
    runKeys.done();
    router.push(`/projects/${project.id}/assessments/${asm.id}`);
  });

  const states: StepState[] = (() => {
    const done = [true, authorized, reviewerSaved, deliverySaved, hasRun];
    const firstOpen = done.indexOf(false);
    return done.map((d, i) => (d ? 'done' : i === firstOpen ? 'current' : 'upcoming'));
  })();
  const st = (i: number): StepState => states[i] ?? 'upcoming';
  const complete = states.filter(s => s === 'done').length;

  return (
    <div className="backdrop-host mx-auto max-w-3xl py-4" data-testid="repo-setup">
      <BackdropShapes />
      <p className="workspace-eyebrow">Setup / {repo.full_name}</p>
      <h1 className="mt-1 text-3xl font-semibold tracking-tight">Let&apos;s set up Ari for {repo.full_name.split('/')[1]}</h1>
      <p className="mt-2 text-sm text-muted">Five short steps. You can change any of this later in Settings.</p>
      <div className="mt-5 h-1.5 overflow-hidden rounded-full bg-panel-2" aria-label={`${complete} of 5 steps done`}>
        <div className="h-full rounded-full bg-brand transition-[width] duration-500" style={{ width: `${complete * 20}%` }} />
      </div>
      {error !== null && <div className="mt-4"><ErrorState error={error} /></div>}
      <ol className="mt-6 space-y-4">
        <Step n={1} state={st(0)} title="Repository connected">
          <p className="text-sm text-muted">Ari can read <span className="font-mono text-ink">{repo.full_name}</span> on <span className="font-mono text-ink">{repo.default_branch}</span> through the GitHub App.</p>
        </Step>
        <Step n={2} state={st(1)} title="Authorize testing">
          <p className="text-sm text-muted">Ari tests a private copy of your code that it builds itself. It never sends traffic to your live site. This authorization lasts 7 days and you can revoke it anytime.</p>
          {scope.kind === 'active' && <p className="mt-2 text-sm font-medium">Authorized. Ari may test this repository in its sandbox.</p>}
          {scope.kind === 'pending' && <Button variant="primary" className="mt-3" disabled={busy !== null} onClick={() => void approveScope(scope.scope.id)}>{busy === 'scope' ? 'Approving…' : 'Approve authorization'}</Button>}
          {scope.kind !== 'active' && scope.kind !== 'pending' && <Button variant="primary" className="mt-3" disabled={busy !== null} onClick={() => void requestScope()}>{busy === 'scope' ? 'Authorizing…' : 'Authorize sandbox testing'}</Button>}
        </Step>
        <Step n={3} state={st(2)} title="Tune the code reviewer">
          <fieldset className="grid gap-2 sm:grid-cols-3">
            <legend className="mb-2 text-sm font-medium">How strict should PR comments be?</legend>
            {STRICTNESS.map(([v, label, hint]) => (
              <label key={v} className={`cursor-pointer rounded-xl border p-3 text-sm transition-colors ${strictness === v ? 'border-brand bg-brand/10' : 'border-line bg-panel hover:border-brand/50'}`}>
                <input type="radio" name="strictness" className="sr-only" checked={strictness === v} onChange={() => setStrictness(v)} />
                <span className="block font-semibold">{label}</span><span className="mt-1 block text-xs text-muted">{hint}</span>
              </label>
            ))}
          </fieldset>
          <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
            <Check checked={monitoring} onChange={setMonitoring} label="Watch this project for new commits" />
            <Check checked={pushes} onChange={setPushes} label="Review pushes to the default branch" />
            <Check checked={prs} onChange={setPrs} label="Review pull requests" />
            <Check checked={comments} onChange={setComments} label="Leave a review comment on pull requests" />
          </div>
          <div className="mt-3"><RepositoryAutomation repoId={repo.id} /></div>
          <p className="text-xs text-muted">Every review, automatic or manual, counts toward this project&apos;s limit of 10 per hour and 50 per day. Branch and author filters are in Settings.</p>
          <Button variant="primary" className="mt-3" disabled={busy !== null} onClick={() => void saveReviewer()}>{busy === 'reviewer' ? 'Saving…' : reviewerSaved ? 'Saved' : 'Save reviewer settings'}</Button>
        </Step>
        <Step n={4} state={st(3)} title="Choose how fixes reach you">
          <div className="grid gap-2">
            {DELIVERY.map(([mode, label, hint]) => (
              <label key={mode} className={`cursor-pointer rounded-xl border p-3 text-sm transition-colors ${delivery === mode ? 'border-brand bg-brand/10' : 'border-line bg-panel hover:border-brand/50'}`}>
                <input type="radio" name="delivery" className="sr-only" checked={delivery === mode} onChange={() => setDelivery(mode)} />
                <span className="block font-semibold">{label}</span><span className="mt-1 block text-xs text-muted">{hint}</span>
              </label>
            ))}
          </div>
          <Button variant="primary" className="mt-3" disabled={busy !== null} onClick={() => void saveDelivery()}>{busy === 'delivery' ? 'Saving…' : deliverySaved ? 'Saved' : 'Save delivery choice'}</Button>
        </Step>
        <Step n={5} state={st(4)} title="Run your first review">
          <p className="text-sm text-muted">Ari&apos;s seven agents review the latest commit on {repo.default_branch}: Scout, Probe, Trace, Diagnose, Patch, Fortify and Verify.</p>
          {hasRun && <p className="mt-2 text-sm"><Link className="font-semibold text-brand" href={`/projects/${project.id}/assessments`}>See your reviews</Link></p>}
          <Button variant="primary" className="mt-3" disabled={busy !== null || !authorized} title={authorized ? undefined : 'Authorize testing first'} onClick={() => void run()}>{busy === 'run' ? 'Starting…' : hasRun ? 'Run another review' : 'Run first review'}</Button>
        </Step>
      </ol>
    </div>
  );
}

function Step({ n, state, title, children }: { n: number; state: StepState; title: string; children: ReactNode }) {
  return (
    <li className={`rounded-2xl border p-5 backdrop-blur-sm transition-all ${state === 'current' ? 'border-brand bg-panel shadow-[0_0_0_4px_rgba(194,69,45,0.18)]' : 'border-line bg-panel/80'} ${state === 'upcoming' ? 'opacity-70' : ''}`} data-step-state={state}>
      <div className="mb-3 flex items-center gap-3">
        <span className={`grid h-8 w-8 place-items-center rounded-full text-sm font-semibold ${state === 'done' ? 'bg-brand text-white' : state === 'current' ? 'border-2 border-brand text-brand' : 'border border-line text-muted'}`}>{state === 'done' ? '✓' : n}</span>
        <h2 className="text-lg font-semibold">{title}</h2>
      </div>
      {children}
    </li>
  );
}

function Check({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return <label className="flex items-center gap-2"><input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} />{label}</label>;
}
