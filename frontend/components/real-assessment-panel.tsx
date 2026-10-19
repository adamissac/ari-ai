'use client';

import type { Assessment, AuthorizedScope, AccessibleRepository } from '@hackatl/frontend-transport';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { ErrorState } from '@/components/ui';
import { api } from '@/lib/api';
import { useActionKeys } from '@/lib/action-key';
import { connectRepo, projectFor } from '@/lib/github-connect';
import { assessmentsForCommit, scopeBody, scopeStateFor } from '@/lib/real-assessment';

type LoadedData =
  | { status: 'error'; error: unknown }
  | {
    status: 'ready';
    projectId: string;
    scopes: AuthorizedScope[];
    assessments: Assessment[];
  };
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
        if (current) {
          setLoaded({
            key: loadKey,
            data: {
              status: 'ready',
              projectId,
              scopes: scopes.items,
              assessments: assessments.items,
            },
          });
        }
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

  const scopeState = data.status === 'ready' && connectedRepoId
    ? scopeStateFor(data.scopes, connectedRepoId, new Date())
    : null;
  const latest = data.status === 'ready' && connectedRepoId
    ? assessmentsForCommit(data.assessments, connectedRepoId, sha)[0]
    : undefined;

  return (
    <div data-testid="real-assessment-panel" className="space-y-3">
      <div className="glass flex flex-wrap items-center justify-between gap-3 px-5 py-4">
        <div>
          <p className="label-mono text-white/55">Real run</p>
          <p className="text-sm text-white/70">
            {!connectedRepoId ? 'Connect this repository to run the 7 agents for real.' : data.status === 'loading' ? 'Loading…' : data.status === 'error' ? 'Could not load the latest run.' : latest ? `Last run: ${latest.state}` : scopeState?.kind === 'none' ? 'Needs an approved authorization before the agents can run.' : scopeState?.kind === 'pending' ? 'Waiting for another project owner to approve.' : 'Authorization is active.'}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {!connectedRepoId && <button type="button" className="rounded-full bg-white px-4 py-2 text-sm font-medium text-ink disabled:opacity-50" disabled={busy} onClick={() => void connect()}>Connect</button>}
          {data.status === 'ready' && latest && (
            <>
              <Link className="text-sm text-white/80 underline-offset-2 hover:underline" href={`/projects/${data.projectId}/assessments/${latest.id}`}>Open run →</Link>
              {scopeState?.kind === 'active' && <button type="button" className="rounded-full bg-white px-4 py-2 text-sm font-medium text-ink disabled:opacity-50" disabled={busy} onClick={() => void startAssessment(data.projectId, scopeState.scope.id)}>Run again</button>}
            </>
          )}
          {data.status === 'ready' && !latest && scopeState?.kind === 'none' && <button type="button" className="rounded-full bg-white px-4 py-2 text-sm font-medium text-ink disabled:opacity-50" disabled={busy} onClick={() => void requestAuthorization(data.projectId)}>Request authorization</button>}
          {data.status === 'ready' && !latest && scopeState?.kind === 'pending' && <Link className="text-sm text-white/80 underline-offset-2 hover:underline" href={`/projects/${data.projectId}/scopes`}>Review</Link>}
          {data.status === 'ready' && !latest && scopeState?.kind === 'active' && (
            <>
              <button type="button" className="rounded-full bg-white px-4 py-2 text-sm font-medium text-ink disabled:opacity-50" disabled={busy} onClick={() => void startAssessment(data.projectId, scopeState.scope.id)}>Run the 7 agents</button>
              <span className="text-xs text-white/50">Uses real Claude spend.</span>
            </>
          )}
        </div>
      </div>
      {data.status === 'error' && <ErrorState error={data.error} onRetry={reload} context="Could not load real assessments" />}
      {actionError !== null && <ErrorState error={actionError} />}
    </div>
  );
}
