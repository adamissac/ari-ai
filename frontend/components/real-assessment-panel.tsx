'use client';

import type { Assessment, AuthorizedScope, AccessibleRepository } from '@hackatl/frontend-transport';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { Button, Empty, ErrorState, Loading, Panel } from '@/components/ui';
import { api } from '@/lib/api';
import { useActionKeys } from '@/lib/action-key';
import { connectRepo, projectFor } from '@/lib/github-connect';
import { assessmentsForCommit, scopeBody, scopeStateFor } from '@/lib/real-assessment';

type LoadedData =
  | { status: 'error'; error: unknown }
  | { status: 'ready'; projectId: string; scopes: AuthorizedScope[]; assessments: Assessment[] };
type DataState = { status: 'loading' } | LoadedData;

export function RealAssessmentPanel({
  org,
  repo,
  sha,
  onConnected,
}: {
  org: string;
  repo: AccessibleRepository;
  sha: string;
  onConnected: () => void;
}) {
  const router = useRouter();
  const [connectedRepoId, setConnectedRepoId] = useState(repo.connected_repo_id);
  const [loaded, setLoaded] = useState<{ key: string; data: LoadedData } | null>(null);
  const [reloadCount, setReloadCount] = useState(0);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<unknown>(null);
  const scopeKeys = useActionKeys('request-scope');
  const assessmentKeys = useActionKeys('start-assessment');
  const loadKey = `${org}|${connectedRepoId ?? ''}|${reloadCount}`;
  const data: DataState = !connectedRepoId || loaded?.key !== loadKey ? { status: 'loading' } : loaded.data;

  useEffect(() => {
    if (!connectedRepoId) return;
    const controller = new AbortController();
    let current = true;
    void projectFor(org)
      .then(async projectId => {
        const [scopes, assessments] = await Promise.all([
          api().scopes(projectId, { signal: controller.signal }),
          api().assessments(projectId, { signal: controller.signal }),
        ]);
        if (current) setLoaded({ key: loadKey, data: { status: 'ready', projectId, scopes: scopes.items, assessments: assessments.items } });
      })
      .catch((error: unknown) => {
        if (current && !controller.signal.aborted) setLoaded({ key: loadKey, data: { status: 'error', error } });
      });
    return () => {
      current = false;
      controller.abort();
    };
  }, [connectedRepoId, loadKey, org]);

  const reload = () => setReloadCount(count => count + 1);
  const connect = async () => {
    setBusy(true);
    setActionError(null);
    try {
      const repoId = await connectRepo(org, repo);
      setConnectedRepoId(repoId);
      onConnected();
    } catch (error) {
      setActionError(error);
    } finally {
      setBusy(false);
    }
  };

  const requestAuthorization = async (projectId: string) => {
    const repoId = connectedRepoId;
    if (!repoId) return;
    setBusy(true);
    setActionError(null);
    const signature = `${projectId}|${repoId}`;
    try {
      const body = scopeKeys.payloadFor(signature, () => scopeBody(repoId, new Date()));
      const created = await api().createScope(projectId, body, { idempotencyKey: scopeKeys.keyFor(signature) });
      scopeKeys.done();
      setLoaded(previous => previous?.key === loadKey && previous.data.status === 'ready'
        ? { ...previous, data: { ...previous.data, scopes: [created, ...previous.data.scopes] } }
        : previous);
    } catch (error) {
      setActionError(error);
    } finally {
      setBusy(false);
    }
  };

  const startAssessment = async (projectId: string, scopeId: string) => {
    const repoId = connectedRepoId;
    if (!repoId) return;
    setBusy(true);
    setActionError(null);
    const signature = `${projectId}|${scopeId}|${repoId}|${sha}`;
    try {
      const body = { scope_id: scopeId, repo_id: repoId, commit_sha: sha, snapshot_id: null, budget: null };
      const assessment = await api().startAssessment(projectId, body, assessmentKeys.keyFor(signature));
      assessmentKeys.done();
      router.push(`/projects/${projectId}/assessments/${assessment.id}`);
    } catch (error) {
      setActionError(error);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div data-testid="real-assessment-panel" className="mb-6">
      <Panel title="Real seven-agent assessment">
        {!connectedRepoId ? (
          <div className="flex flex-col items-start gap-3">
            <p className="text-sm text-muted">Connect this GitHub repository to the project before starting a backend assessment.</p>
            <Button variant="primary" disabled={busy} onClick={() => void connect()}>Connect</Button>
          </div>
        ) : data.status === 'loading' ? (
          <Loading label="Loading project scopes and assessments" />
        ) : data.status === 'error' ? (
          <ErrorState error={data.error} onRetry={reload} context="Could not load real assessments" />
        ) : (
          <AssessmentReady
            data={data}
            repoId={connectedRepoId}
            sha={sha}
            busy={busy}
            onRequestAuthorization={() => void requestAuthorization(data.projectId)}
            onStart={scopeId => void startAssessment(data.projectId, scopeId)}
          />
        )}
        {actionError !== null && <div className="mt-3"><ErrorState error={actionError} /></div>}
      </Panel>
    </div>
  );
}

function AssessmentReady({
  data,
  repoId,
  sha,
  busy,
  onRequestAuthorization,
  onStart,
}: {
  data: Extract<DataState, { status: 'ready' }>;
  repoId: string;
  sha: string;
  busy: boolean;
  onRequestAuthorization: () => void;
  onStart: (scopeId: string) => void;
}) {
  const scopeState = scopeStateFor(data.scopes, repoId, new Date());
  const assessments = assessmentsForCommit(data.assessments, repoId, sha);

  return (
    <div className="flex flex-col gap-4">
      <section aria-label="Assessments for this commit">
        <h3 className="mb-2 text-sm font-semibold text-ink">Assessments for this commit</h3>
        {assessments.length === 0 ? <Empty>No real backend assessment has been recorded for this commit yet.</Empty> : (
          <ul className="flex flex-col gap-2">
            {assessments.map(assessment => (
              <li key={assessment.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-line bg-panel-2/50 px-3 py-2 text-sm">
                <Link className="text-brand hover:underline" href={`/projects/${data.projectId}/assessments/${assessment.id}`}>
                  Assessment <code>{assessment.id}</code>
                </Link>
                <span className="text-muted">{assessment.state}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {scopeState.kind === 'none' ? (
        <div className="flex flex-col items-start gap-3">
          <p className="text-sm text-muted">No active or pending authorization covers this repository.</p>
          <Button variant="primary" disabled={busy} onClick={onRequestAuthorization}>Request authorization</Button>
        </div>
      ) : scopeState.kind === 'pending' ? (
        <div className="flex flex-col items-start gap-2 text-sm">
          <p className="text-muted">A different project owner must approve this scope before any agent runs. The requester cannot approve their own scope.</p>
          <Link className="text-brand hover:underline" href={`/projects/${data.projectId}/scopes`}>Review project scopes</Link>
        </div>
      ) : (
        <div className="flex flex-col items-start gap-3">
          <Button variant="primary" disabled={busy} onClick={() => onStart(scopeState.scope.id)}>
            Run the seven agents on {sha.slice(0, 7)}
          </Button>
          <p className="text-xs text-muted">Uses the project budget (default cap $10); costs real Claude spend.</p>
        </div>
      )}

      <p className="text-xs text-muted">
        Probe can only run executed checks when the repository has a <code>build_recipe.json</code>; without it validation is inconclusive, and Patch/Verify run only on confirmed findings.
      </p>
    </div>
  );
}
