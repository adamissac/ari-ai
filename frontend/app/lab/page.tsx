'use client';

import { useEffect, useState } from 'react';
import { ReplayStage } from '@/components/lab-replay';
import { Term } from '@/components/term';
import { Empty, ErrorState, Field, inputClass, Loading, Mono, Panel } from '@/components/ui';
import { defenderCountPhrase, machineCountPhrase } from '@/components/lab-copy';
import { num } from '@/lib/format';
import { domain, HIGHER_IS_BETTER, METRIC_LABEL, metricNames, metricRows, sampleSize } from '@/lib/lab';
import { keyTakeaway, POLICY_NAME, policyName, scenarioName, SCORE_METRICS, scoreboard, type ScoreMetric, tradeoffNote } from '@/lib/lab-plain';
import type { BundleResponse, DefenseLabBundle, LabEpisode } from '@/lib/lab-types';

type Load<T> = { status: 'loading' } | { status: 'ready'; data: T } | { status: 'error'; error: unknown };

async function getJson<T>(url: string, signal: AbortSignal): Promise<T> {
  const res = await fetch(url, { signal, cache: 'no-store' });
  const body = await res.json() as T & { error?: string };
  if (!res.ok) throw new Error(body.error ?? `HTTP ${res.status}`);
  return body;
}

export default function DefenseLabPage() {
  const [protocols, setProtocols] = useState<Load<string[]>>({ status: 'loading' });
  const [protocol, setProtocol] = useState('');
  const [loaded, setLoaded] = useState<{ protocol: string; result: Load<BundleResponse> } | null>(null);
  const bundle: Load<BundleResponse> = loaded && loaded.protocol === protocol ? loaded.result : { status: 'loading' };

  useEffect(() => {
    const c = new AbortController();
    getJson<{ protocols: string[] }>('/lab/bundles', c.signal).then(
      d => { setProtocols({ status: 'ready', data: d.protocols }); setProtocol(p => p || d.protocols[0] || ''); },
      (error: unknown) => { if (!c.signal.aborted) setProtocols({ status: 'error', error }); },
    );
    return () => c.abort();
  }, []);

  useEffect(() => {
    if (!protocol) return;
    const c = new AbortController();
    getJson<BundleResponse>(`/lab/bundles/${encodeURIComponent(protocol)}`, c.signal).then(
      data => setLoaded({ protocol, result: { status: 'ready', data } }),
      (error: unknown) => { if (!c.signal.aborted) setLoaded({ protocol, result: { status: 'error', error } }); },
    );
    return () => c.abort();
  }, [protocol]);

  return (
    <>
      <header className="hero-ink mb-6 rounded-2xl px-6 py-8 md:px-10 md:py-10">
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div className="max-w-2xl">
            <p className="label-mono text-white/60">Defense Lab · research</p>
            <h1 className="display mt-3 text-3xl font-semibold md:text-5xl">Can an AI learn to defend a network?</h1>
            <p className="mt-4 text-sm text-white/75 md:text-base">
              We trained an AI defender in a practice network and tested it against simpler defenders on games it never saw. This page shows the scores and lets you replay real recorded games.
            </p>
          </div>
          {protocols.status === 'ready' && protocols.data.length > 0 && (
            <div className="lab-run-picker">
              <Field label="Evaluation run">
                <select className={inputClass} value={protocol} onChange={e => setProtocol(e.target.value)} name="protocol">
                  {protocols.data.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
              </Field>
            </div>
          )}
        </div>
      </header>
      {protocols.status === 'loading' && <Loading label="Finding evaluation runs" />}
      {protocols.status === 'error' && <ErrorState error={protocols.error} context="Could not list evaluation runs" />}
      {protocols.status === 'ready' && protocols.data.length === 0 && <Empty>No committed evaluation bundle (rl-defense/results/protocol-*/defense_lab.json) was found.</Empty>}
      {protocol && bundle.status === 'loading' && <Loading label={`Loading ${protocol}`} />}
      {bundle.status === 'error' && <ErrorState error={bundle.error} context="Evaluation bundle rejected" />}
      {bundle.status === 'ready' && <Lab data={bundle.data} />}
    </>
  );
}

const GAME_STEPS: { n: string; title: string; body: (machines: string) => string }[] = [
  { n: '01', title: 'A pretend network', body: machines => `${machines.charAt(0).toUpperCase()}${machines.slice(1).replace(/machines?$/, m => `fake ${m}`)}, some reachable from the internet, some holding critical data.` },
  { n: '02', title: 'A simulated attacker', body: () => 'It sneaks in and tries to reach a critical machine without being stopped.' },
  { n: '03', title: 'A defender choosing moves', body: () => 'Each step it chooses from a fixed set of moves, such as watching, slowing traffic or cutting a machine off.' },
];

function Lab({ data }: { data: BundleResponse }) {
  const { bundle, provenance } = data;
  return (
    <div className="flex flex-col gap-16">
      <section aria-labelledby="lab-what" data-testid="lab-intro" className="paper py-14 md:py-16">
        <h2 id="lab-what" className="sr-only">What is this?</h2>
        <p className="lab-lede">
          A practice game (a <Term t="simulation">simulation</Term>). An AI defender learned by trial and error a <Term t="policy">policy</Term>:
          which moves keep the intruder out without shutting the business down.
        </p>
        <ol className="mt-5 grid gap-3 md:grid-cols-3">
          {GAME_STEPS.map(step => (
            <li key={step.n} className="lab-step">
              <span className="lab-step-n" aria-hidden="true">{step.n}</span>
              <p className="mt-4 font-semibold tracking-tight">{step.title}</p>
              <p className="mt-1 text-sm text-muted">{step.body(machineCountPhrase(bundle.scenarios))}</p>
            </li>
          ))}
        </ol>
        <p role="note" className="lab-caveat mt-4" data-testid="lab-caveat">
          <svg viewBox="0 0 16 16" className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round"><path d="M8 1.8 14.6 13.5H1.4z" strokeLinejoin="round" /><path d="M8 6.3v3.4M8 11.7v.01" /></svg>
          <span><strong>Simulation only{bundle.simulation_only ? '' : ' (flag missing!)'}.</strong> {bundle.caveat} This is not real network detection and no action is ever applied automatically.</span>
        </p>
      </section>
      <Replay bundle={bundle} />
      <Scoreboard bundle={bundle} />
      <details className="group rounded-2xl border border-line bg-panel" data-testid="lab-details">
        <summary className="flex cursor-pointer list-none items-center gap-2 px-5 py-4 text-sm font-semibold">
          <span aria-hidden="true" className="inline-block transition-transform group-open:rotate-90">▸</span>
          For reviewers: every metric, per scenario, and where these numbers come from
        </summary>
        <div className="flex flex-col gap-4 border-t border-line p-5">
          <Panel title="Provenance">
            <dl className="grid gap-x-4 gap-y-1 text-xs text-muted sm:grid-cols-[auto_1fr]">
              <dt>Source</dt><dd><Mono>{provenance.path}</Mono> — committed evaluation artifact, validated against <Mono>{provenance.schemaPath}</Mono>. Not yet served by the backend API.</dd>
              <dt>Bundle sha256</dt><dd><Mono>{provenance.sha256}</Mono> ({(provenance.bytes / 1024 / 1024).toFixed(2)} MB)</dd>
              <dt>Environment</dt><dd><Mono>{bundle.env_id}</Mono> · schema {bundle.schema_version}</dd>
              <dt>Run</dt><dd><Mono>{bundle.source_run}</Mono> at commit <Mono>{bundle.git_sha.slice(0, 12)}</Mono></dd>
              <dt>Training seeds</dt><dd>{bundle.training_seeds.join(', ')} · {bundle.episodes_per_config_per_seed} episodes per held-out config per seed</dd>
              <dt>Checkpoints</dt>
              <dd className="flex flex-col">{Object.entries(bundle.checkpoint_sha256).map(([f, h]) => <span key={f}><Mono>{f}</Mono> sha256 <Mono>{h.slice(0, 16)}…</Mono></span>)}</dd>
            </dl>
          </Panel>
          <Metrics bundle={bundle} />
        </div>
      </details>
    </div>
  );
}

const HEADLINE: readonly { key: string; label: string; vs: string }[] = [
  { key: 'compromise_rate', label: 'of attacks reached their goal', vs: 'noop' },
  { key: 'service_uptime', label: 'of the time services stayed up', vs: 'threshold_rules' },
  { key: 'time_to_containment', label: 'steps on average to contain', vs: 'threshold_rules' },
];

const fmtScore = (metric: ScoreMetric, x: number | null) => (x === null ? '—' : metric.percent ? `${x.toFixed(1)}%` : x.toFixed(1));
const fmtRange = (metric: ScoreMetric, lo: number | null, hi: number | null) =>
  lo === null || hi === null ? '—' : `${lo.toFixed(1)}–${hi.toFixed(1)}${metric.percent ? '%' : ''}`;

function Headline({ bundle }: { bundle: DefenseLabBundle }) {
  const tiles = HEADLINE.flatMap(h => {
    const metric = SCORE_METRICS.find(m => m.key === h.key);
    if (!metric) return [];
    const cells = scoreboard(bundle, metric);
    const ai = cells.find(c => c.policy === 'ddqn');
    if (!ai || ai.value === null) return [];
    const vs = cells.find(c => c.policy === h.vs);
    return [{ metric, label: h.label, ai, vs }];
  });
  if (tiles.length === 0) return null;
  return (
    <dl className="lab-headline mt-6" data-testid="lab-takeaway" aria-label={keyTakeaway(bundle) ?? undefined}>
      {tiles.map(({ metric, label, ai, vs }) => (
        <div key={metric.key} className="lab-headline-tile">
          <dt className="sr-only">Trained AI defender: {metric.title}</dt>
          <dd>
            <span className="lab-headline-num">{fmtScore(metric, ai.value)}</span>
            <span className="mt-1 block text-sm text-ink">{label}</span>
            {vs && vs.value !== null && (
              <span className="mt-2 block text-xs text-muted">vs {fmtScore(metric, vs.value)} for {policyName(vs.policy).toLowerCase()}</span>
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function Direction({ higher }: { higher: boolean }) {
  return (
    <span className="inline-flex items-center gap-1 whitespace-nowrap text-xs text-faint">
      <svg viewBox="0 0 12 12" className="h-3 w-3" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
        {higher ? <path d="M6 10V2M2.5 5.5 6 2l3.5 3.5" /> : <path d="M6 2v8M2.5 6.5 6 10l3.5-3.5" />}
      </svg>
      {higher ? 'Higher is better' : 'Lower is better'}
    </span>
  );
}

function Scoreboard({ bundle }: { bundle: DefenseLabBundle }) {
  const n = sampleSize(bundle, null);
  const tradeoff = tradeoffNote(bundle);
  return (
    <section aria-labelledby="score-title" data-testid="lab-scoreboard" className="paper py-14 md:py-20">
      <p className="lab-eyebrow">02 · Compare</p>
      <h2 id="score-title" className="mt-2 text-2xl font-semibold tracking-tight md:text-3xl">Who defends best?</h2>
      <p className="mt-2 max-w-3xl text-sm text-muted">
        {defenderCountPhrase(bundle.metrics.length, true)}, each tested on {n.toLocaleString()} games they never trained on. The shaded band on each bar is the 95% range the true average very likely falls in.
      </p>
      <Headline bundle={bundle} />
      <div className="mt-8 grid grid-cols-1 gap-4 lg:grid-cols-2">
        {SCORE_METRICS.map(metric => {
          const cells = scoreboard(bundle, metric);
          if (cells.every(c => c.value === null)) return null;
          const top = Math.max(...cells.map(x => x.hi ?? x.value ?? 0), 1);
          const pct = (x: number | null) => (x === null ? 0 : Math.min(100, Math.max(0, metric.percent ? x : (x / top) * 100)));
          return (
            <figure key={metric.key} className="lab-score-card" data-testid={`score-${metric.key}`}>
              <figcaption>
                <span className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                  <span className="font-semibold tracking-tight text-ink">{metric.title}</span>
                  <Direction higher={metric.higherIsBetter} />
                </span>
                <span className="mt-1 block text-xs leading-relaxed text-muted">{metric.explain}</span>
              </figcaption>
              <ul className="mt-5 flex flex-col gap-4">
                {cells.map(c => {
                  const ai = c.policy === 'ddqn';
                  return (
                    <li key={c.policy} className="lab-score-row" data-ai={ai || undefined}>
                      <span className="lab-score-name" title={POLICY_NAME[c.policy]?.note}>
                        {policyName(c.policy)}
                        {c.best && <span className="lab-best">Best</span>}
                      </span>
                      <span className="lab-score-track" aria-hidden="true">
                        {c.lo !== null && c.hi !== null && <span className="lab-score-band" style={{ left: `${pct(c.lo)}%`, width: `${Math.max(0.6, pct(c.hi) - pct(c.lo))}%` }} />}
                        <span className="lab-score-bar" style={{ width: `${pct(c.value)}%` }} />
                      </span>
                      <span className="lab-score-value">
                        {fmtScore(metric, c.value)}
                        <span className="lab-score-range"><span className="sr-only">95% range </span>{fmtRange(metric, c.lo, c.hi)}</span>
                      </span>
                    </li>
                  );
                })}
              </ul>
            </figure>
          );
        })}
      </div>
      {tradeoff && (
        <p className="mt-5 flex items-start gap-2.5 text-sm text-muted" data-testid="lab-tradeoff">
          <svg viewBox="0 0 16 16" className="mt-0.5 h-4 w-4 shrink-0 text-brand" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth={1.5}><circle cx="8" cy="8" r="6.5" /><path d="M8 7.2v4M8 4.8v.01" strokeLinecap="round" /></svg>
          <span>{tradeoff}</span>
        </p>
      )}
      <dl className="lab-defenders mt-6">
        {bundle.metrics.map(m => (
          <div key={m.policy}>
            <dt>{policyName(m.policy)}</dt>
            <dd>{POLICY_NAME[m.policy]?.note ?? 'Policy id from the bundle.'}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function Metrics({ bundle }: { bundle: DefenseLabBundle }) {
  const names = metricNames(bundle);
  const [metric, setMetric] = useState(names[0] ?? 'return');
  const [scenario, setScenario] = useState<string>('');
  const rows = metricRows(bundle, metric, scenario || null);
  const [min, max] = domain(rows);
  const x = (v: number) => ((v - min) / (max - min)) * 100;
  const n = sampleSize(bundle, scenario || null);
  return (
    <Panel title="Held-out evaluation: policy vs baselines" actions={
      <div className="flex flex-wrap gap-2">
        <select aria-label="Metric" className={inputClass} value={metric} onChange={e => setMetric(e.target.value)}>
          {names.map(m => <option key={m} value={m}>{METRIC_LABEL[m] ?? m}</option>)}
        </select>
        <select aria-label="Scenario" className={inputClass} value={scenario} onChange={e => setScenario(e.target.value)}>
          <option value="">All held-out scenarios (pooled)</option>
          {bundle.scenarios.map(s => <option key={s.name} value={s.name}>{s.name}</option>)}
        </select>
      </div>
    }>
      <p className="mb-3 text-xs text-muted">
        Mean with 95% confidence interval over n = {n.toLocaleString()} evaluation episodes per policy ({bundle.training_seeds.length} training seeds × {bundle.episodes_per_config_per_seed} episodes{scenario ? '' : ` × ${bundle.scenarios.length} scenarios`}).
        {' '}{HIGHER_IS_BETTER.has(metric) ? 'Higher is better.' : 'Lower is better.'}
      </p>
      <figure aria-label={`${METRIC_LABEL[metric] ?? metric} by policy`} className="flex flex-col gap-2" data-testid="metric-chart">
        {rows.map(r => (
          <div key={r.policy} className="grid grid-cols-[4.5rem_minmax(0,1fr)_auto] items-center gap-2 text-xs sm:grid-cols-[8rem_minmax(0,1fr)_13rem]">
            <span className={`min-w-0 [overflow-wrap:anywhere] ${r.policy === 'ddqn' ? 'font-semibold text-accent' : 'text-muted'}`}>{r.policy}</span>
            <svg viewBox="0 0 100 10" preserveAspectRatio="none" className="h-5 w-full" role="img" aria-label={`${r.policy}: ${r.mean === null ? 'no value' : num(r.mean, 3)}`}>
              <line x1={x(0)} x2={x(0)} y1={0} y2={10} stroke="var(--color-line)" strokeWidth={0.4} />
              {r.mean !== null && <rect x={Math.min(x(0), x(r.mean))} width={Math.abs(x(r.mean) - x(0))} y={2.5} height={5} fill={r.policy === 'ddqn' ? 'var(--color-brand)' : 'var(--color-faint)'} opacity={r.policy === 'ddqn' ? 0.9 : 0.55} />}
              {r.lo !== null && r.hi !== null && (
                <g stroke="var(--color-ink)" strokeWidth={0.5}>
                  <line x1={x(r.lo)} x2={x(r.hi)} y1={5} y2={5} />
                  <line x1={x(r.lo)} x2={x(r.lo)} y1={2} y2={8} />
                  <line x1={x(r.hi)} x2={x(r.hi)} y1={2} y2={8} />
                </g>
              )}
            </svg>
            <span className="font-mono text-muted sm:whitespace-nowrap">{r.mean === null ? 'n/a' : num(r.mean, 3)} <span className="text-faint">[{r.lo === null ? '—' : num(r.lo, 2)}, {r.hi === null ? '—' : num(r.hi, 2)}]</span></span>
          </div>
        ))}
        <figcaption className="text-xs text-faint">Axis {num(min, 2)} … {num(max, 2)}. Values are copied from the bundle; nothing is recomputed in the browser.</figcaption>
      </figure>
    </Panel>
  );
}

function Replay({ bundle }: { bundle: DefenseLabBundle }) {
  const policies = [...new Set(bundle.episodes.map(e => e.policy))];
  const scenarios = [...new Set(bundle.episodes.map(e => e.scenario))];
  const [policy, setPolicy] = useState(policies.includes('ddqn') ? 'ddqn' : policies[0] ?? '');
  const [scenarioId, setScenarioId] = useState(scenarios[0] ?? '');
  const index = Math.max(0, bundle.episodes.findIndex(e => e.policy === policy && e.scenario === scenarioId));
  const episode: LabEpisode | undefined = bundle.episodes[index];
  const scenario = bundle.scenarios.find(s => s.name === episode?.scenario);
  return (
    <section aria-labelledby="replay-title">
      <p className="lab-eyebrow">01 · Watch</p>
      <h2 id="replay-title" className="mt-2 text-2xl font-semibold tracking-tight md:text-3xl">Replay a recorded game</h2>
      <p className="mt-2 max-w-3xl text-sm text-muted">Pick a defender and an attacker, press play, and follow what the defender saw and did at each step.</p>
      {!episode || !scenario ? <div className="mt-4"><Empty>This bundle has no recorded episodes.</Empty></div> : (
        <div className="lab-replay-card mt-6">
          <div className="flex flex-wrap items-end justify-between gap-4 border-b border-line px-5 py-4">
            <div role="group" aria-label="Defender" className="lab-segment">
              {policies.map(p => (
                <button key={p} type="button" aria-pressed={p === policy} onClick={() => setPolicy(p)} className="lab-segment-btn">{policyName(p)}</button>
              ))}
            </div>
            <label className="flex flex-col gap-1 text-xs text-muted">
              Attacker
              <select aria-label="Attacker scenario" className={inputClass} value={scenarioId} onChange={e => setScenarioId(e.target.value)}>
                {scenarios.map(s => <option key={s} value={s}>{scenarioName(s)}</option>)}
              </select>
            </label>
          </div>
          <div className="p-5"><ReplayStage key={index} episode={episode} scenario={scenario} /></div>
        </div>
      )}
    </section>
  );
}
