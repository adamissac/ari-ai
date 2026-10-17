'use client';

import { ApiError, type Assessment, type AssessmentState, type Repository, type Snapshot, type StreamEvent } from '@hackatl/frontend-transport';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState, type FormEvent } from 'react';
import { PillarLoop } from '@/components/pillar-loop';
import { useProject } from '@/components/project';
import { Async, Badge, Button, Empty, ErrorState, Field, inputClass, Mono, Panel, Stat, Time } from '@/components/ui';
import { api, idempotencyKey } from '@/lib/api';
import { CONNECT_REPOSITORY_NOTE } from '@/lib/connect';
import { INDEX_COMMIT_NOTE } from '@/lib/index-commit';
import { shortSha, usd } from '@/lib/format';
import {
  EVENT_LOG_PAGE_NOTE, JOURNEY_STATUS, fullEventLog, latestAssessmentEvent,
  projectJourney, statesFromLog,
} from '@/lib/journey';
import { projectOverview } from '@/lib/overview';
import { pillarLoop } from '@/lib/pillars';
import { START_ASSESSMENT_NOTE } from '@/lib/start-assessment';
import { ASSESSMENT_STATE, FINDING_STATUS, SNAPSHOT_STATUS, TERMINAL_STATES } from '@/lib/status';
import { useResource } from '@/lib/use-resource';

const SHA = /^[0-9a-f]{7,40}$/;

export default function ProjectOverview() {
  const { project, repos } = useProject();
  const assessments = useResource(`asm:${project.id}`, s => api().assessments(project.id, { signal: s }), 5000);
  const findings = useResource(`fnd:${project.id}`, s => api().findings(project.id, { signal: s }), 10000);
  const scopes = useResource(`scopes:${project.id}`, s => api().scopes(project.id, { signal: s }));
  const assessmentItems = assessments.status === 'ready' ? assessments.data.items : [];
  const findingItems = findings.status === 'ready' ? findings.data.items : [];
  const scopeItems = scopes.status === 'ready' ? scopes.data.items : [];
  // Null (unknown) until scopes have loaded; never zero by default.
  const activeScopeCount = scopes.status === 'ready' ? scopeItems.filter(s => s.status === 'active').length : null;
  const summary = projectOverview({
    projectId: project.id,
    repoCount: repos.length,
    activeScopeCount,
    monitoringEnabled: project.settings.monitoring_policy.enabled,
    assessments: assessmentItems,
    findings: findingItems,
  });
  const ready = assessments.status === 'ready' && findings.status === 'ready' && scopes.status === 'ready';
  const failed = [assessments, findings, scopes].filter(r => r.status === 'error');
  const refreshFailed = [assessments, findings, scopes].some(r => r.refreshError !== undefined);
  return (
    <div className="flex flex-col gap-4">
      <section aria-label="Project summary" className="rounded-xl border border-line bg-panel p-5" data-testid="project-summary">
        {failed.length > 0 ? (
          <ErrorState
            error={failed[0]?.error}
            onRetry={() => failed.forEach(r => r.reload())}
            context={`Summary unavailable: ${[assessments, findings, scopes].map((r, i) => (r.status === 'error' ? ['assessments', 'findings', 'scopes'][i] : null)).filter(Boolean).join(', ')} did not load`}
          />
        ) : ready ? (
          <>
            <h2 className="text-xl font-semibold tracking-tight">{summary.headline}</h2>
            <p className="mt-2 max-w-3xl text-sm text-muted">{summary.detail}</p>
            <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-3">
              <Stat label="Code health" value={summary.codeOpen} hint="open functional findings" />
              <Stat label="Security" value={summary.securityOpen} hint={`confirmed weaknesses${summary.untested ? ` · ${summary.untested} untested suspicion${summary.untested === 1 ? '' : 's'}` : ''}${summary.inconclusive ? ` · ${summary.inconclusive} inconclusive` : ''}`} />
              <Stat label="Continuous defense" value={summary.monitoring} hint={`${summary.verifiedFixes} verified fixes`} />
            </div>
            {refreshFailed && <p role="status" className="mt-3 text-xs text-warn" data-testid="summary-stale">Could not refresh the latest records. The numbers above are from the last successful load and may be out of date.</p>}
            <div className="mt-4">
              <a href={summary.action.href} className="inline-flex items-center rounded-full bg-brand px-4 py-2 text-sm font-medium text-on-brand hover:bg-brand-deep">{summary.action.label}</a>
            </div>
          </>
        ) : <p className="text-sm text-muted">Loading the current project records…</p>}
      </section>
      <PillarLoopSection
        projectId={project.id}
        repoCount={repos.length}
        activeScopeCount={activeScopeCount}
        monitoringEnabled={project.settings.monitoring_policy.enabled}
        assessmentCount={assessments.status === 'ready' ? assessmentItems.length : null}
        findings={findings.status === 'ready' ? findingItems : null}
      />
      {ready && activeScopeCount !== null && (
        <ProjectJourney
          projectId={project.id}
          repoCount={repos.length}
          activeScopeCount={activeScopeCount}
          monitoringEnabled={project.settings.monitoring_policy.enabled}
          assessments={assessmentItems}
          findingStatuses={findingItems.map(f => f.status)}
        />
      )}
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[3fr_2fr]">
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
    </div>
  );
}

function PillarLoopSection(props: {
  projectId: string; repoCount: number; activeScopeCount: number | null; monitoringEnabled: boolean;
  assessmentCount: number | null; findings: readonly { kind: string; status: string }[] | null;
}) {
  const monitoring = useResource(`loop-mon:${props.projectId}`, signal => api().monitoringEvents(props.projectId, { signal }), 15000);
  const reassess = useResource(`loop-re:${props.projectId}`, signal => api().reassessments(props.projectId, { signal }), 15000);
  return (
    <PillarLoop nodes={pillarLoop({
      ...props,
      monitoringEventCount: monitoring.status === 'ready' ? monitoring.data.items.length : null,
      reassessmentCount: reassess.status === 'ready' ? reassess.data.items.length : null,
    })} />
  );
}

function ProjectJourney({
  projectId, repoCount, activeScopeCount, monitoringEnabled, assessments, findingStatuses,
}: {
  projectId: string;
  repoCount: number;
  activeScopeCount: number;
  monitoringEnabled: boolean;
  assessments: readonly Assessment[];
  findingStatuses: readonly string[];
}) {
  const latest = [...assessments].sort((a, b) => (a.created_at < b.created_at ? 1 : -1))[0] ?? null;
  // The log grows while the check runs, so poll it until the latest check is terminal. The state is
  // part of the key so a phase change refetches at once and `visited` never lags the badge.
  const latestRunning = latest !== null && !TERMINAL_STATES.has(latest.state);
  const events = useResource(
    `journey-events:${latest?.id ?? 'none'}:${latest?.state ?? 'none'}`,
    signal => latest
      ? fullEventLog(after => api().eventsLog(latest.id, after, { signal }))
      : Promise.resolve({ items: [], truncated: false }),
    latestRunning ? 5000 : undefined,
  );
  // Keep showing the previous log of the same check while the next one loads, instead of flashing "Loading".
  const [lastLog, setLastLog] = useState<{ id: string; items: StreamEvent[]; truncated: boolean } | null>(null);
  if (events.status === 'ready' && latest && lastLog?.items !== events.data.items) {
    setLastLog({ id: latest.id, items: events.data.items, truncated: events.data.truncated });
  }
  const shownLog = events.status === 'ready' ? events.data : lastLog && lastLog.id === latest?.id ? lastLog : null;
  const logItems = shownLog?.items ?? null;
  const monitoring = useResource(
    `journey-mon:${projectId}`,
    signal => api().monitoringEvents(projectId, { signal }),
    15000,
  );
  const logReady = latest === null || events.status !== 'loading' || logItems !== null;
  const visited = logItems ? statesFromLog(logItems) : null;
  const logTruncated = shownLog?.truncated === true;
  const monitoringItems = monitoring.status === 'ready' ? monitoring.data.items : [];
  const stages = projectJourney({
    repoCount,
    activeScopeCount,
    current: (latest?.state ?? null) as AssessmentState | null,
    visited: logReady ? visited : null,
    findingStatuses,
    monitoringEnabled,
    monitoringKnown: monitoring.status === 'ready',
    monitoringEventCount: monitoringItems.length,
    monitoringTruncated: monitoringItems.length >= 50,
    monitoringFailed: monitoringItems.some(event => event.status === 'failed'),
    newestMonitoringSimulated: monitoringItems[0]?.simulated === true,
    eventLogTruncated: logTruncated,
  });
  const latestEvent = logItems ? latestAssessmentEvent(logItems) : null;
  const assessmentHref = latest ? `/projects/${projectId}/assessments/${latest.id}` : null;

  return (
    <section aria-label="Check progress" className="rounded-xl border border-line bg-panel p-5" data-testid="project-journey">
      <h2 className="text-sm font-semibold tracking-tight">Where this check is</h2>
      {!logReady ? <p className="mt-2 text-sm text-muted">Loading the recorded phases…</p> : (
        <>
          {logTruncated && (
            <p className="mt-2 text-sm text-muted" data-testid="event-log-page-note">{EVENT_LOG_PAGE_NOTE}</p>
          )}
          <ol className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {stages.map(item => {
              const href = item.id === 'monitor' ? `/projects/${projectId}/monitoring` : assessmentHref;
              return (
                <li key={item.id} className="rounded-lg border border-line p-3" data-testid={`journey-${item.id}`}>
                  <p className="text-sm font-medium">{item.label}</p>
                  <p className="text-xs text-muted">{JOURNEY_STATUS[item.status]}</p>
                  <p className="mt-1 text-xs text-muted">{item.detail}</p>
                  {href && <Link className="mt-2 inline-block text-xs text-accent hover:underline" href={href}>Open</Link>}
                </li>
              );
            })}
          </ol>
        </>
      )}
      {latestEvent && (
        <p className="mt-3 text-sm text-muted" data-testid="project-latest-event">
          Latest recorded event: {latestEvent.message} <Time iso={latestEvent.at} />
        </p>
      )}
      {events.status === 'ready' && events.refreshError !== undefined && <p role="status" className="mt-3 text-xs text-warn">Could not refresh the event log. The phases shown are from the last successful load.</p>}
      {events.status === 'error' && <div className="mt-3"><ErrorState error={events.error} onRetry={events.reload} context="Event log" /></div>}
      {monitoring.status === 'error' && <div className="mt-3"><ErrorState error={monitoring.error} onRetry={monitoring.reload} context="Monitoring events" /></div>}
    </section>
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
  const conflict = error instanceof ApiError && error.status === 409 && error.error.code === 'IDEMPOTENCY_CONFLICT';

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const sig = `${project.id}|${repoId}|${scopeId}|${sha.trim()}`;
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
    <Panel title="Start an assessment" id="start-assessment">
      <p className="mb-3 text-sm text-muted" data-testid="start-assessment-note">{START_ASSESSMENT_NOTE}</p>
      {repos.length === 0 ? <Empty>Connect a repository first.</Empty> : (
        <form onSubmit={submit} className="grid grid-cols-1 gap-3 sm:grid-cols-3">
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
          <div className="sm:col-span-3">
            <Button type="submit" variant="primary" disabled={busy || !repoId || !scopeId || (sha !== '' && !SHA.test(sha))}>Start assessment</Button>
          </div>
          {error !== null && <div className="sm:col-span-3">
            <ErrorState error={error} context="Assessment not started" />
            {conflict && <div className="mt-2 text-sm">
              <p>Check the assessment list before starting a separate action. The previous key belongs to another request; retrying unchanged will keep returning this conflict.</p>
              <Button type="button" className="mt-2" disabled={busy} onClick={() => { setKey(null); setError(null); }}>
                Prepare a new assessment action
              </Button>
              <p className="mt-1 text-xs text-muted">This only resets the action key. Press Start assessment to submit a new action; it may create another assessment.</p>
            </div>}
          </div>}
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
    <Panel title="Repositories" id="connect-repo">
      <p className="mb-3 text-sm text-muted" data-testid="connect-repository-note">{CONNECT_REPOSITORY_NOTE}</p>
      {repos.length === 0 ? <Empty>No repository connected.</Empty> : (
        <>
        <p className="mb-3 text-sm text-muted" data-testid="index-commit-note">{INDEX_COMMIT_NOTE}</p>
        <ul className="flex flex-col gap-3">
          {repos.map(r => <RepoRow key={r.id} repo={r} />)}
        </ul>
        </>
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

