'use client';

import type { DefenseRecommendation, MonitoringEvent, RLExplanation } from '@hackatl/frontend-transport';
import Link from 'next/link';
import { useState } from 'react';
import { AttackDrill } from '@/components/attack-drill';
import { useProject } from '@/components/project';
import { Async, Badge, Button, Empty, ErrorState, Loading, Mono, Panel, Tag, Time } from '@/components/ui';
import { api } from '@/lib/api';
import { num, shortSha } from '@/lib/format';
import { monitoringSummary } from '@/lib/monitoring';
import { EVENT_STATUS } from '@/lib/status';
import { useResource } from '@/lib/use-resource';

const RL_CAVEAT = 'Recommendation from a policy trained in simulation. Not applied automatically.';

export default function MonitoringPage() {
  const { project } = useProject();
  const events = useResource(`events:${project.id}`, s => api().monitoringEvents(project.id, { signal: s }), 10000);
  const reassess = useResource(`reassess:${project.id}`, s => api().reassessments(project.id, { signal: s }), 10000);
  const recs = useResource(`recs:${project.id}`, s => api().defenseRecommendations(project.id, { signal: s }));
  const evals = useResource(`rle:${project.id}`, s => api().rlEvaluations(project.id, { signal: s }));
  const summary = monitoringSummary({
    monitoringEnabled: project.settings.monitoring_policy.enabled,
    eventsKnown: events.status === 'ready',
    eventCount: events.status === 'ready' ? events.data.items.length : 0,
    simulatedCount: events.status === 'ready' ? events.data.items.filter(event => event.simulated).length : 0,
    eventsTruncated: events.status === 'ready' && events.data.items.length >= 50,
    recommendationsKnown: recs.status === 'ready',
    recommendationCount: recs.status === 'ready' ? recs.data.items.length : 0,
  });
  return (
    <div className="flex flex-col gap-4">
      <header className="monitor-head" data-testid="monitor-head">
        <div>
          <p className="label-mono text-white/60">Continuous defense monitor</p>
          <h2 className="mt-1 text-xl font-semibold tracking-tight text-white">What we have recorded for this project</h2>
          <p className="mt-1 max-w-2xl text-sm text-white/70">Real events from your connected repository and runtime, plus re-checks they triggered. This is a record of what arrived, not a promise of round-the-clock protection.</p>
        </div>
        <ul className="monitor-chips" aria-label="Monitoring status">
          <li><span className="text-white/50">Monitoring</span> {project.settings.monitoring_policy.enabled ? 'on' : 'off'}</li>
          <li><span className="text-white/50">Events</span> {events.status === 'ready' ? `${events.data.items.length}${events.data.items.length >= 50 ? '+' : ''}` : '…'}</li>
          <li><span className="text-white/50">Simulated events</span> {events.status === 'ready' ? events.data.items.filter(e => e.simulated).length : '…'}</li>
          <li><span className="text-white/50">Re-checks</span> {reassess.status === 'ready' ? reassess.data.items.length : '…'}</li>
        </ul>
      </header>
      <p className="rounded-xl border border-line bg-panel p-5 text-sm text-ink" data-testid="monitoring-summary">{summary}</p>
      <AttackDrill projectId={project.id} onEvents={events.reload} />
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-[3fr_2fr]">
      <div className="flex flex-col gap-4">
        <Panel title="Event feed" actions={<span className="text-xs text-muted">persisted webhook and runtime events · polled every 10 s</span>}>
          <Async resource={events} label="monitoring events">
            {page => <EventFeed items={page.items} />}
          </Async>
        </Panel>
        <Panel title="Re-assessment requests">
          <Async resource={reassess} label="re-assessments">
            {page => page.items.length === 0 ? <Empty>No re-assessments requested by monitoring.</Empty> : (
              <ul className="divide-y divide-line text-sm">
                {page.items.map(r => (
                  <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                    <span className="flex flex-wrap items-center gap-2">
                      <Tag tone={r.status === 'blocked_no_scope' ? 'warn' : r.status === 'started' ? 'ok' : 'neutral'}>{r.status.replaceAll('_', ' ')}</Tag>
                      <Tag>{r.scope}</Tag> head <Mono>{shortSha(r.head_sha)}</Mono> · {r.event_ids.length} event{r.event_ids.length === 1 ? '' : 's'}
                    </span>
                    <span className="text-xs text-muted">
                      {r.assessment_id ? <Link className="font-mono text-accent hover:underline" href={`/projects/${project.id}/assessments/${r.assessment_id}`}>{r.assessment_id}</Link> : r.reason} · <Time iso={r.created_at} />
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Async>
        </Panel>
      </div>
      <div className="flex flex-col gap-4">
        <Panel title="Defense recommendations (simulation-derived)">
          <p className="mb-3 rounded border border-warn/40 bg-warn/10 px-2 py-1.5 text-xs text-warn" data-testid="rl-caveat">{RL_CAVEAT}</p>
          <Async resource={recs} label="recommendations">
            {page => (
              <>
                <p className="mb-2 text-xs text-faint">Backend label: {page.label}</p>
                {page.items.length === 0 ? <Empty>No recommendation has been requested for this project.</Empty> : (
                  <ul className="flex flex-col gap-2">{page.items.map(r => <Recommendation key={r.id} rec={r} />)}</ul>
                )}
              </>
            )}
          </Async>
        </Panel>
        <Panel title="Imported RL evaluations">
          <Async resource={evals} label="RL evaluations">
            {page => page.items.length === 0 ? <Empty>No evaluation imported into this project. The <Link className="text-accent hover:underline" href="/lab">Defense Lab</Link> reads the committed evaluation bundle directly.</Empty> : (
              <ul className="divide-y divide-line text-xs">
                {page.items.map(e => (
                  <li key={e.id} className="py-2">
                    <Mono>{e.id}</Mono> · protocol {e.protocol_version} · {e.checkpoint_ids.length} checkpoints · summary sha256 <Mono>{e.summary_sha256.slice(0, 12)}</Mono> · <Time iso={e.created_at} />
                  </li>
                ))}
              </ul>
            )}
          </Async>
        </Panel>
      </div>
    </div>
    </div>
  );
}

function EventFeed({ items }: { items: MonitoringEvent[] }) {
  const { project } = useProject();
  if (items.length === 0) {
    return <Empty>No events received. Monitoring shows only signed GitHub deliveries or authenticated runtime batches that actually reached the backend.</Empty>;
  }
  const last = items[0];
  return (
    <>
      <p className="mb-2 text-xs text-muted">Last received <Time iso={last?.received_at} /> · {items.length} most recent events</p>
      <ol className="flex flex-col gap-2" data-testid="monitoring-feed">
        {items.map(e => (
          <li key={e.id} className="rounded-md border border-line bg-panel-2 p-2.5 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <Tag tone="accent">{e.source}</Tag>
              <Tag>{e.type.replace('_', ' ')}</Tag>
              {e.simulated && <Tag tone="warn">replayed / fixture event</Tag>}
              <Badge view={EVENT_STATUS[e.status]} />
              <span className="text-xs text-muted">{e.ref ?? ''}{e.pr_number ? ` · PR #${e.pr_number}` : ''} · received <Time iso={e.received_at} /></span>
            </div>
            {e.commit_range && <p className="mt-1 text-xs text-muted">commits <Mono>{shortSha(e.commit_range.base_sha)}</Mono> → <Mono>{shortSha(e.commit_range.head_sha)}</Mono></p>}
            {e.status_reason && <p className="mt-1 text-xs text-muted">{e.status_reason}</p>}
            {e.impact && (
              <p className="mt-1 text-xs text-muted">
                Impact ({e.impact.resolution === 'symbol' ? 'symbol-level' : 'path-only'}): {e.impact.changed_paths.length} paths, {e.impact.symbols.length} symbols, {e.impact.expectations.length} expectations,{' '}
                {e.impact.findings.length > 0 ? <>findings {e.impact.findings.map(f => <Link key={f} className="font-mono text-accent hover:underline" href={`/projects/${project.id}/findings/${f}`}>{f} </Link>)}</> : '0 findings'}, {e.impact.regression_tests.length} regression tests
              </p>
            )}
          </li>
        ))}
      </ol>
    </>
  );
}

function Recommendation({ rec }: { rec: DefenseRecommendation }) {
  const [exp, setExp] = useState<{ status: 'idle' } | { status: 'loading' } | { status: 'ready'; data: RLExplanation } | { status: 'error'; error: unknown }>({ status: 'idle' });
  const explain = async () => {
    setExp({ status: 'loading' });
    try { setExp({ status: 'ready', data: await api().recommendationExplanation(rec.id) }); } catch (error) { setExp({ status: 'error', error }); }
  };
  return (
    <li className="rounded-md border border-line bg-panel-2 p-2.5 text-xs">
      <p className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-semibold">{rec.action.replaceAll('_', ' ')}</span>{rec.node && <Tag>{rec.node}</Tag>}
        <span className="text-xs text-muted">Q-margin {num(rec.q_margin, 3)}</span>
      </p>
      <p className="mt-1 text-muted">policy <Mono>{rec.policy_version}</Mono> · checkpoint <Mono>{rec.checkpoint_sha256.slice(0, 12)}</Mono> · <Time iso={rec.created_at} /></p>
      <p className="mt-1 text-warn">{rec.caveat}</p>
      {exp.status === 'idle' && (
        <Button className="mt-1 !px-2 !py-0.5 text-xs" onClick={() => void explain()}>Why this action?</Button>
      )}
      {exp.status === 'loading' && <Loading label="Loading explanation" />}
      {exp.status === 'error' && <ErrorState error={exp.error} onRetry={() => void explain()} context="Explanation" />}
      {exp.status === 'ready' && (
        <div className="mt-1">
          <p className="text-muted">Method {exp.data.method} · runner-up {exp.data.runner_up ?? '—'} · margin {num(exp.data.margin, 3)}</p>
          <ul className="mt-1">
            {exp.data.top_contributions.map((c, i) => (
              <li key={i} className={c.delta_margin > 0 ? 'text-ok' : 'text-bad'}>
                {c.delta_margin > 0 ? 'supports' : 'opposes'} · <Mono>{c.node ? `${c.node}.` : ''}{c.feature}</Mono> = {num(c.value, 3)} (Δmargin {num(c.delta_margin, 3)}, {c.kind})
              </li>
            ))}
          </ul>
        </div>
      )}
    </li>
  );
}
