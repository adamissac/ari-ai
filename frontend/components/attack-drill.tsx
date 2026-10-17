'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { DemoMarker } from '@/components/demo/ui';
import { Button, ErrorState, Mono, Panel, Tag } from '@/components/ui';
import { api } from '@/lib/api';
import { parseDrillResult, TECHNIQUE_LABEL, type DrillResult } from '@/lib/attack-drill';

type State = { kind: 'idle' } | { kind: 'running'; jobId: string } | { kind: 'done'; result: DrillResult } | { kind: 'error'; error: unknown };

/**
 * Labelled simulated attack (ADR 0013): Claude plans an attack on this project's real
 * routes, the drill's synthetic traffic goes through the real detection pipeline, and the
 * defense response is a recommendation only. Nothing is sent to the repository or executed.
 */
export function AttackDrill({ projectId, onEvents }: { projectId: string; onEvents: () => void }) {
  const [state, setState] = useState<State>({ kind: 'idle' });

  useEffect(() => {
    if (state.kind !== 'running') return;
    const controller = new AbortController();
    const t = setInterval(() => {
      api().job(state.jobId, { signal: controller.signal }).then(job => {
        if (job.status === 'succeeded') {
          const result = parseDrillResult(job.result);
          setState(result ? { kind: 'done', result } : { kind: 'error', error: new Error('The drill returned an unexpected result') });
          onEvents();
        } else if (job.status === 'failed' || job.status === 'dead') {
          setState({ kind: 'error', error: new Error(job.error ?? 'The drill failed') });
        }
      }, (err: unknown) => { if (!controller.signal.aborted) setState({ kind: 'error', error: err }); });
    }, 1500);
    return () => { clearInterval(t); controller.abort(); };
  }, [state, onEvents]);

  const start = async () => {
    try { setState({ kind: 'running', jobId: (await api().startAttackDrill(projectId)).job_id }); }
    catch (err) { setState({ kind: 'error', error: err }); }
  };

  return (
    <Panel title="Attack drill" actions={<DemoMarker />}>
      <p className="text-sm text-muted">Claude plays an attacker against this repository&apos;s real routes. Ari&apos;s detection scores the drill&apos;s simulated traffic and recommends a response. No traffic reaches your service and nothing is executed.</p>
      <div className="mt-3">
        <Button variant="primary" onClick={() => void start()} disabled={state.kind === 'running'} data-testid="attack-drill-start">
          {state.kind === 'running' ? 'Claude is attacking…' : state.kind === 'done' ? 'Run another drill' : 'Run an attack drill'}
        </Button>
      </div>
      {state.kind === 'error' && <div className="mt-3"><ErrorState error={state.error} context="Attack drill failed" /></div>}
      {state.kind === 'done' && <DrillReport projectId={projectId} r={state.result} />}
    </Panel>
  );
}

function DrillReport({ projectId, r }: { projectId: string; r: DrillResult }) {
  return (
    <div className="mt-4 flex flex-col gap-4 text-sm" data-testid="attack-drill-report">
      <section>
        <p className="label-mono text-faint">1 · Attack {r.planAuthor === 'claude' ? 'planned by Claude' : '(scripted plan; Claude unavailable)'}</p>
        <p className="mt-1 font-semibold text-ink">{r.plan.attacker}: {TECHNIQUE_LABEL[r.plan.technique] ?? r.plan.technique} on <Mono>{r.plan.route}</Mono></p>
        <p className="mt-1 text-muted">{r.plan.narrative}</p>
        <ol className="mt-2 list-decimal pl-5 text-muted">{r.plan.steps.map(s => <li key={s}>{s}</li>)}</ol>
      </section>
      <section>
        <p className="label-mono text-faint">2 · Detection</p>
        <p className="mt-1">
          {r.detection.detected ? <Tag tone="warn">Detected</Tag> : <Tag>Not detected</Tag>}{' '}
          anomaly score <Mono>{r.detection.anomalyScore.toFixed(2)}</Mono>
        </p>
        {r.detection.reasons.length > 0 && <ul className="mt-1 list-disc pl-5 text-muted">{r.detection.reasons.map(x => <li key={x}>{x}</li>)}</ul>}
        {r.detection.linkedFindings.length > 0 && (
          <p className="mt-1 text-muted">Linked to open findings: {r.detection.linkedFindings.map(f => <Link key={f} className="font-mono text-accent hover:underline" href={`/projects/${projectId}/findings/${f}`}>{f} </Link>)}</p>
        )}
      </section>
      <section>
        <p className="label-mono text-faint">3 · Defense response <span className="normal-case">({r.response.responder}; recommended, not executed)</span></p>
        {r.response.actions.length === 0 ? <p className="mt-1 text-muted">No response needed.</p> : (
          <ul className="mt-1 flex flex-col gap-1.5">{r.response.actions.map(a => <li key={a.action + a.detail}><span className="font-medium text-ink">{a.action}.</span> <span className="text-muted">{a.detail}</span></li>)}</ul>
        )}
      </section>
    </div>
  );
}
