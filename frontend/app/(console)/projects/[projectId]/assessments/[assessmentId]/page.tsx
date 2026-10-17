'use client';

import { watchAssessment, type AgentRun, type Approval, type AssessmentDetail, type AssessmentState, type ConnectionState, type StreamEvent } from '@hackatl/frontend-transport';
import Link from 'next/link';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParam, useProject } from '@/components/project';
import { useSession } from '@/components/session';
import { Badge, Button, Empty, ErrorState, Loading, Mono, PageTitle, Panel, Stat, Tag, Time } from '@/components/ui';
import { api } from '@/lib/api';
import { duration, shortSha, usd } from '@/lib/format';
import {
  AGENT_RUN_STATUS, AGENTS, agentRole, APPROVAL_STATUS, ASSESSMENT_STATE, FINDING_STATUS, providerLabel,
  railSteps, SEVERITY, TERMINAL_STATES,
} from '@/lib/status';

const CONNECTION: Record<ConnectionState, { label: string; tone: 'ok' | 'warn' | 'bad' | 'info' | 'neutral' }> = {
  connecting: { label: 'Connecting to event stream', tone: 'info' },
  connected: { label: 'Live: receiving persisted events', tone: 'ok' },
  reconnecting: { label: 'Reconnecting (resumes from last event)', tone: 'warn' },
  completed: { label: 'Stream complete: run reached a terminal state', tone: 'neutral' },
  aborted: { label: 'Stream closed', tone: 'neutral' },
  failed: { label: 'Stream failed', tone: 'bad' },
};

export default function AssessmentPage() {
  const id = useParam('assessmentId');
  const { project } = useProject();
  const [detail, setDetail] = useState<AssessmentDetail | null>(null);
  const [detailError, setDetailError] = useState<unknown>(null);
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [connection, setConnection] = useState<ConnectionState>('connecting');
  const [streamError, setStreamError] = useState<unknown>(null);
  const [streamNonce, setStreamNonce] = useState(0);
  const refreshTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const loadDetail = useCallback(async (signal?: AbortSignal) => {
    try {
      setDetail(await api().assessment(id, signal ? { signal } : {}));
      setDetailError(null);
    } catch (err) {
      if (!signal?.aborted) setDetailError(err);
    }
  }, [id]);

  useEffect(() => {
    const controller = new AbortController();
    void loadDetail(controller.signal);
    return () => controller.abort();
  }, [loadDetail]);

  // Records change only when an event says so; coalesce bursts into one refetch.
  const scheduleRefresh = useCallback(() => {
    if (refreshTimer.current) clearTimeout(refreshTimer.current);
    refreshTimer.current = setTimeout(() => void loadDetail(), 250);
  }, [loadDetail]);

  useEffect(() => {
    const controller = new AbortController();
    let cursor = 0;
    setStreamError(null);
    (async () => {
      for await (const event of watchAssessment(api(), id, { after: cursor, signal: controller.signal, onConnection: setConnection })) {
        cursor = event.seq;
        setEvents(prev => (prev.some(e => e.seq === event.seq) ? prev : [...prev, event].sort((a, b) => a.seq - b.seq)));
        scheduleRefresh();
      }
      scheduleRefresh();
    })().catch((err: unknown) => {
      if (!controller.signal.aborted) setStreamError(err);
    });
    return () => controller.abort();
  }, [id, streamNonce, scheduleRefresh]);

  useEffect(() => () => { if (refreshTimer.current) clearTimeout(refreshTimer.current); }, []);

  if (detailError && !detail) return <ErrorState error={detailError} onRetry={() => void loadDetail()} context="Could not load assessment" />;
  if (!detail) return <Loading label="Loading assessment" />;
  const a = detail.assessment;
  const terminal = TERMINAL_STATES.has(a.state);

  return (
    <>
      <PageTitle
        title={<span className="flex flex-wrap items-center gap-2">Assessment <Mono className="text-base">{a.id}</Mono> <Badge view={ASSESSMENT_STATE[a.state]} /></span>}
        subtitle={<>Commit <Mono>{shortSha(a.commit_sha)}</Mono> · {a.trigger} trigger · scope <Mono>{a.scope_id}</Mono> · started <Time iso={a.created_at} />{a.completed_at && <> · ended <Time iso={a.completed_at} /></>}</>}
        actions={!terminal && <CancelButton id={a.id} onDone={() => void loadDetail()} />}
      />
      <ConnectionBar state={connection} error={streamError} onReconnect={() => setStreamNonce(n => n + 1)} />
      {a.error && (
        <div role="alert" className="mb-4 rounded-md border border-bad/40 bg-bad/5 p-3 text-sm">
          <p className="font-semibold text-bad">Assessment error · {a.error.code}</p>
          <p className="text-muted">{a.error.message}</p>
        </div>
      )}
      <ProviderSummary runs={detail.agent_runs} />
      <StateRail state={a.state} events={events} />
      <div className="mt-4 grid gap-3 sm:grid-cols-4">
        <Stat label="Tokens" value={`${(a.usage.input_tokens + a.usage.output_tokens).toLocaleString()}`} hint={`cap ${a.budget.max_tokens.toLocaleString()}`} />
        <Stat label="Model cost" value={usd(a.usage.usd)} hint={`cap ${usd(a.budget.max_usd)}`} />
        <Stat label="Model / tool calls" value={`${a.usage.llm_calls} / ${a.usage.tool_calls}`} />
        <Stat label="Sandbox time" value={`${a.usage.sandbox_seconds.toFixed(1)} s`} hint={`wall cap ${a.budget.max_wall_clock_s}s`} />
      </div>
      <BudgetMeter used={a.usage.usd} cap={a.budget.max_usd} />
      {a.state === 'AWAITING_APPROVAL' && <ApprovalGate projectId={project.id} events={events} onDecided={() => void loadDetail()} />}
      <div className="mt-4 grid gap-4 xl:grid-cols-[3fr_2fr]">
        <Panel title="Runtime agents" actions={<span className="text-xs text-muted">one persisted record per agent execution</span>}>
          <AgentLanes runs={detail.agent_runs} />
        </Panel>
        <div className="flex flex-col gap-4">
          <Panel title={`Findings (${detail.findings.length})`}>
            {detail.findings.length === 0 ? <Empty>{terminal ? 'No findings were recorded by this run.' : 'No findings recorded yet.'}</Empty> : (
              <ul className="divide-y divide-line">
                {detail.findings.map(f => (
                  <li key={f.id} className="py-2">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <Link href={`/projects/${project.id}/findings/${f.id}`} className="text-sm font-medium hover:text-accent">{f.title}</Link>
                      <Badge view={FINDING_STATUS[f.status]} />
                    </div>
                    <p className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-muted">
                      <Tag tone={f.kind === 'security' ? 'bad' : 'info'}>{f.kind}</Tag>
                      {f.severity && <Badge view={SEVERITY[f.severity.level]} />}
                      confidence {(f.confidence * 100).toFixed(0)}% · {f.evidence.length} evidence refs
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
          <Panel title={`Event log (${events.length})`} actions={<a className="text-xs text-accent hover:underline" href={`/api/v1/assessments/${a.id}/report`} target="_blank" rel="noreferrer">JSON report</a>}>
            <EventLog events={events} />
          </Panel>
        </div>
      </div>
    </>
  );
}

function ConnectionBar({ state, error, onReconnect }: { state: ConnectionState; error: unknown; onReconnect: () => void }) {
  const c = CONNECTION[state];
  return (
    <div className="mb-4 flex flex-col gap-2">
      <p className="flex items-center gap-2 text-xs" data-testid="stream-state">
        <Badge view={{ label: c.label, tone: c.tone, glyph: state === 'connected' ? '●' : '○' }} />
      </p>
      {error !== null && <ErrorState error={error} onRetry={onReconnect} context="Event stream" />}
    </div>
  );
}

function ProviderSummary({ runs }: { runs: AgentRun[] }) {
  const modes = new Map<string, number>();
  for (const r of runs) modes.set(r.provider_mode, (modes.get(r.provider_mode) ?? 0) + 1);
  if (modes.size === 0) return null;
  const notLive = [...modes.keys()].some(m => m !== 'live');
  return (
    <div className={`mb-4 rounded-md border px-3 py-2 text-sm ${notLive ? 'border-warn/50 bg-warn/10' : 'border-ok/40 bg-ok/5'}`} data-testid="provider-summary">
      <span className="font-semibold">{notLive ? 'Not a live-provider run. ' : 'Live provider run. '}</span>
      Model turns came from: {[...modes].map(([m, n]) => `${providerLabel(m).label} × ${n}`).join(', ')}.
      {notLive && <span className="text-muted"> Tool execution, sandbox checks, tests and persistence are still real; the model replies were scripted.</span>}
    </div>
  );
}

function StateRail({ state, events }: { state: AssessmentState; events: StreamEvent[] }) {
  const visited = useMemo(() => new Set(events.map(e => e.state).filter((s): s is AssessmentState => s !== null)), [events]);
  const steps = railSteps(state, visited);
  const failed = state === 'FAILED' || state === 'CANCELLED' || state === 'BUDGET_EXHAUSTED';
  return (
    <ol aria-label="Assessment state" className="flex flex-wrap gap-1">
      {steps.map(s => {
        const cls = {
          done: 'border-ok/40 bg-ok/10 text-ok',
          current: 'border-accent bg-accent/15 text-accent',
          upcoming: 'border-line text-faint',
          skipped: 'border-dashed border-line text-faint line-through',
        }[s.phase];
        return (
          <li key={s.state} aria-current={s.phase === 'current' ? 'step' : undefined} className={`rounded border px-2 py-1 text-xs ${cls}`}>
            <span className="sr-only">{s.phase}: </span>{ASSESSMENT_STATE[s.state].label}
          </li>
        );
      })}
      {failed && <li className="rounded border border-bad/50 bg-bad/10 px-2 py-1 text-xs text-bad">{ASSESSMENT_STATE[state].label}</li>}
    </ol>
  );
}

function BudgetMeter({ used, cap }: { used: number; cap: number }) {
  const ratio = cap > 0 ? Math.min(1, used / cap) : 0;
  return (
    <div className="mt-2" aria-label="Budget used">
      <div className="h-1.5 w-full overflow-hidden rounded bg-panel-2" role="meter" aria-valuemin={0} aria-valuemax={cap} aria-valuenow={used} aria-label="Model spend against cap">
        <div className={`h-full ${ratio > 0.9 ? 'bg-bad' : ratio > 0.6 ? 'bg-warn' : 'bg-accent'}`} style={{ width: `${ratio * 100}%` }} />
      </div>
    </div>
  );
}

function AgentLanes({ runs }: { runs: AgentRun[] }) {
  return (
    <ol className="flex flex-col gap-3">
      {AGENTS.map(role => {
        const mine = runs.filter(r => r.agent === role.name);
        return (
          <li key={role.name} className="rounded-md border border-line bg-panel-2 p-3" data-testid={`agent-${role.name}`}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <span className="font-semibold">{role.label}</span>
                <span className="ml-2 text-xs text-faint">{role.team} · {role.role}</span>
              </div>
              {mine.length === 0 && <span className="text-xs text-faint">no run recorded</span>}
            </div>
            {mine.map(run => <RunCard key={run.id} run={run} />)}
          </li>
        );
      })}
      {runs.filter(r => !AGENTS.some(a => a.name === r.agent)).map(run => <RunCard key={run.id} run={run} />)}
    </ol>
  );
}

function RunCard({ run }: { run: AgentRun }) {
  const [open, setOpen] = useState(false);
  const provider = providerLabel(run.provider_mode);
  const denied = run.tool_calls.filter(t => t.outcome === 'denied').length;
  const errors = run.tool_calls.filter(t => t.outcome === 'error').length;
  return (
    <div className="mt-2 border-t border-line pt-2 text-xs">
      <div className="flex flex-wrap items-center gap-2">
        <Badge view={AGENT_RUN_STATUS[run.status]} />
        <Badge view={provider} />
        <Mono>{run.step_key}</Mono>
        {run.attempt > 1 && <Tag tone="warn">attempt {run.attempt}</Tag>}
        <span className="text-muted">{duration(run.started_at, run.ended_at)} · {(run.usage.input_tokens + run.usage.output_tokens).toLocaleString()} tokens · {usd(run.usage.usd)} · {run.usage.llm_calls} model turns</span>
      </div>
      <p className="mt-1 text-muted">
        model <Mono>{run.model_id ?? '—'}</Mono> · prompt <Mono>{run.prompt_version ?? '—'}</Mono> · {run.tool_calls.length} tool calls
        {denied > 0 && <span className="text-warn"> · {denied} denied by policy</span>}
        {errors > 0 && <span className="text-bad"> · {errors} errored</span>}
      </p>
      {run.error && <p className="mt-1 text-bad">{run.error.code}: {run.error.message}</p>}
      {run.tool_calls.length > 0 && (
        <button type="button" className="mt-1 text-accent hover:underline" aria-expanded={open} onClick={() => setOpen(o => !o)}>
          {open ? 'Hide' : 'Show'} tool trace
        </button>
      )}
      {open && (
        <table className="mt-1 w-full text-left">
          <thead className="text-faint"><tr><th className="pr-2">turn</th><th className="pr-2">tool</th><th className="pr-2">outcome</th><th className="pr-2">ms</th><th>input sha256</th></tr></thead>
          <tbody>
            {run.tool_calls.map((t, i) => (
              <tr key={i} className="border-t border-line/60">
                <td className="pr-2">{t.turn}</td>
                <td className="pr-2"><Mono>{t.tool_name}</Mono></td>
                <td className={`pr-2 ${t.outcome === 'ok' ? 'text-ok' : t.outcome === 'denied' ? 'text-warn' : 'text-bad'}`}>{t.outcome}{t.error_code ? ` (${t.error_code})` : ''}</td>
                <td className="pr-2">{t.duration_ms}</td>
                <td><Mono>{t.input_sha256.slice(0, 12)}</Mono></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function ApprovalGate({ projectId, events, onDecided }: { projectId: string; events: StreamEvent[]; onDecided: () => void }) {
  const { me } = useSession();
  const [approvals, setApprovals] = useState<Approval[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const requested = useMemo(() => new Set(events.map(e => e.approval_id).filter((x): x is string => !!x)), [events]);
  const load = useCallback(() => {
    api().pendingApprovals(projectId).then(p => setApprovals(p.items.filter(a => requested.has(a.id))), setError);
  }, [projectId, requested]);
  useEffect(load, [load]);
  const decide = async (ap: Approval, decision: 'approved' | 'declined') => {
    setBusy(true);
    setError(null);
    try { await api().decideApproval(ap.id, { decision, reason: null }); onDecided(); load(); }
    catch (err) { setError(err); } finally { setBusy(false); }
  };
  return (
    <Panel title="Human approval required" className="mt-4 border-warn/50">
      <p className="text-sm text-muted">The orchestrator paused before remediation. Approving lets Patch build a candidate fix in an isolated worktree and Verify re-test it in a fresh sandbox. Nothing is merged or deployed.</p>
      {approvals === null && !error && <Loading label="Loading approval" />}
      {approvals?.length === 0 && <Empty>No pending approval found for this run.</Empty>}
      {approvals?.map(ap => (
        <div key={ap.id} className="mt-3 flex flex-wrap items-center gap-2 text-sm">
          <Badge view={APPROVAL_STATUS[ap.status]} /> <Mono>{ap.subject_type}:{ap.subject_id}</Mono>
          <span className="text-xs text-muted">requested by {ap.requested_by ?? 'system'} <Time iso={ap.requested_at} /></span>
          <Button variant="primary" disabled={busy || ap.requested_by === me.user.id} onClick={() => void decide(ap, 'approved')}>Approve remediation</Button>
          <Button variant="danger" disabled={busy} onClick={() => void decide(ap, 'declined')}>Decline</Button>
        </div>
      ))}
      {error !== null && <div className="mt-2"><ErrorState error={error} context="Approval" /></div>}
    </Panel>
  );
}

function CancelButton({ id, onDone }: { id: string; onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  return (
    <div className="flex flex-col items-end gap-1">
      <Button variant="danger" disabled={busy} onClick={async () => {
        setBusy(true);
        setError(null);
        try { await api().cancelAssessment(id); onDone(); } catch (err) { setError(err); } finally { setBusy(false); }
      }}>Cancel assessment</Button>
      {error !== null && <ErrorState error={error} context="Cancel" />}
    </div>
  );
}

function EventLog({ events }: { events: StreamEvent[] }) {
  if (events.length === 0) return <Empty>No events yet.</Empty>;
  return (
    <ol className="max-h-[28rem] overflow-y-auto text-xs" aria-live="polite" data-testid="event-log">
      {events.map(e => (
        <li key={e.seq} className="grid grid-cols-[2.5rem_1fr] gap-2 border-b border-line/60 py-1.5">
          <span className="font-mono text-faint">#{e.seq}</span>
          <div>
            <p className="flex flex-wrap items-center gap-1.5">
              <Mono>{e.type}</Mono>
              {e.agent && <Tag tone="accent">{agentRole(e.agent).label}</Tag>}
              {e.state && <Tag>{ASSESSMENT_STATE[e.state].label}</Tag>}
              <span className="text-faint"><Time iso={e.at} /></span>
            </p>
            <p className="mt-0.5 text-muted">{e.message}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}
