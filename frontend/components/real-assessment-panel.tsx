'use client';

import type { Assessment, AuthorizedScope, AccessibleRepository } from '@hackatl/frontend-transport';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { ErrorState } from '@/components/ui';
import { api } from '@/lib/api';
import { useActionKeys } from '@/lib/action-key';
import { connectRepo, projectForRepository } from '@/lib/github-connect';
import { assessmentsForCommit, loadCommitAssessments, isSandboxOnlyScope, scopeBody, scopeStateFor } from '@/lib/real-assessment';
import { ASSESSMENT_STATE } from '@/lib/status';
import { useResource } from '@/lib/use-resource';

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
  onRunSelected,
}: {
  org: string;
  repo: AccessibleRepository;
  sha: string;
  onConnected: () => void;
  onRunSelected?: (assessmentId: string) => void;
}) {
  const router = useRouter();
  const [connectedRepoId, setConnectedRepoId] = useState(repo.connected_repo_id);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<unknown>(null);
  const scopeKeys = useActionKeys('request-scope');
  const assessmentKeys = useActionKeys('start-assessment');
  const resource = useResource(connectedRepoId ? `real-run:${org}:${connectedRepoId}:${sha}` : null, async signal => {
    const projectId = await projectForRepository(connectedRepoId!, signal);
    const [scopes, assessments] = await Promise.all([
      api().scopes(projectId, { signal }),
      loadCommitAssessments(cursor => api().assessments(projectId, { signal, ...(cursor ? { cursor } : {}) }), connectedRepoId!, sha),
    ]);
    return { projectId, scopes: scopes.items, assessments };
  }, 10000);
  const data: DataState = resource.status === 'ready'
    ? { status: 'ready', ...resource.data }
    : resource.status === 'error' ? { status: 'error', error: resource.error } : { status: 'loading' };
  const reload = resource.reload;
  useEffect(() => {
    window.addEventListener('focus', reload);
    return () => window.removeEventListener('focus', reload);
  }, [reload]);

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
      await api().createScope(projectId, body, { idempotencyKey: scopeKeys.keyFor(signature) });
      scopeKeys.done();
      reload();
    } catch (error) {
      setActionError(error);
    } finally {
      setBusy(false);
    }
  };

  const approveAuthorization = async (scopeId: string) => {
    setBusy(true);
    setActionError(null);
    try {
      await api().approveScope(scopeId);
      reload();
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
      if (onRunSelected) { onRunSelected(assessment.id); reload(); }
      else router.push(`/projects/${projectId}/assessments/${assessment.id}`);
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

  const latestId = latest?.id;
  useEffect(() => { if (latestId && onRunSelected) onRunSelected(latestId); }, [latestId, onRunSelected]);

  return (
    <div data-testid="real-assessment-panel" className="space-y-3">
      <div className="glass flex flex-wrap items-center justify-between gap-3 px-5 py-4">
        <div>
          <p className="label-mono text-white/55">Real run</p>
          <p className="text-sm text-white/70" aria-live="polite">
            {!connectedRepoId ? 'Connect this repository to run the 7 agents for real.' : data.status === 'loading' ? 'Loading…' : data.status === 'error' ? 'Could not load the latest run.' : latest ? `Last run: ${ASSESSMENT_STATE[latest.state].label}` : scopeState?.kind === 'none' ? 'Needs an approved authorization before the agents can run.' : scopeState?.kind === 'pending' ? isSandboxOnlyScope(scopeState.scope) ? 'A project owner can approve this sandbox-only authorization.' : 'Waiting for another project owner to approve.' : 'Authorization is active.'}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {!connectedRepoId && <button type="button" className="rounded-full bg-white px-4 py-2 text-sm font-medium text-ink disabled:opacity-50" disabled={busy} onClick={() => void connect()}>Connect</button>}
          {data.status === 'ready' && latest && (
            <>
              {onRunSelected ? <button type="button" className="text-sm text-white/80 underline-offset-2 hover:underline" onClick={() => onRunSelected(latest.id)}>Open recorded run</button> : <Link className="text-sm text-white/80 underline-offset-2 hover:underline" href={`/projects/${data.projectId}/assessments/${latest.id}`}>Open run →</Link>}
              {scopeState?.kind === 'active' && <button type="button" className="rounded-full bg-white px-4 py-2 text-sm font-medium text-ink disabled:opacity-50" disabled={busy} onClick={() => void startAssessment(data.projectId, scopeState.scope.id)}>Run again</button>}
            </>
          )}
          {data.status === 'ready' && !latest && scopeState?.kind === 'none' && <button type="button" className="rounded-full bg-white px-4 py-2 text-sm font-medium text-ink disabled:opacity-50" disabled={busy} onClick={() => void requestAuthorization(data.projectId)}>Request authorization</button>}
          {data.status === 'ready' && scopeState?.kind === 'pending' && (
            <>
              {isSandboxOnlyScope(scopeState.scope) && <button type="button" className="rounded-full bg-white px-4 py-2 text-sm font-medium text-ink disabled:opacity-50" disabled={busy || resource.refreshError !== undefined} onClick={() => void approveAuthorization(scopeState.scope.id)}>Approve sandbox authorization</button>}
              <Link className="text-sm text-white/80 underline-offset-2 hover:underline" href={`/projects/${data.projectId}/scopes`}>Review authorization</Link>
              <button type="button" className="text-sm text-white/80 underline-offset-2 hover:underline" onClick={reload}>Refresh status</button>
            </>
          )}
          {data.status === 'ready' && !latest && scopeState?.kind === 'active' && (
            <>
              <button type="button" className="rounded-full bg-white px-4 py-2 text-sm font-medium text-ink disabled:opacity-50" disabled={busy} onClick={() => void startAssessment(data.projectId, scopeState.scope.id)}>Run the 7 agents</button>
              <span className="text-xs text-white/50">Uses real Claude spend.</span>
            </>
          )}
        </div>
      </div>
      {data.status === 'error' && <ErrorState error={data.error} onRetry={reload} context="Could not load real assessments" />}
      {resource.refreshError !== undefined && <ErrorState error={resource.refreshError} onRetry={reload} context="Status refresh failed; showing the last loaded run" />}
      {actionError !== null && <ErrorState error={actionError} />}
    </div>
  );
}
