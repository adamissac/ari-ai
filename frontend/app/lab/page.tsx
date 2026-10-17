'use client';

import { useEffect, useMemo, useState } from 'react';
import { NodeGraph } from '@/components/node-graph';
import { Term } from '@/components/term';
import { Badge, Button, Empty, ErrorState, Field, inputClass, Loading, Mono, Panel, Tag } from '@/components/ui';
import { defenderCountPhrase, machineCountPhrase } from '@/components/lab-copy';
import { num } from '@/lib/format';
import { cumulativeReturn, domain, episodeLabel, episodeStory, HIGHER_IS_BETTER, METRIC_LABEL, metricNames, metricRows, rewardTotals, sampleSize, stepObservation } from '@/lib/lab';
import { actionInWords, episodeOutcome, episodeTimeline, keyTakeaway, POLICY_NAME, policyName, rewardWord, SCENARIO_WORDS, scenarioName, SCORE_METRICS, scoreboard, STAGE_WORDS, tradeoffNote } from '@/lib/lab-plain';
import type { BundleResponse, DefenseLabBundle, LabEpisode, LabNodeState, LabScenario } from '@/lib/lab-types';

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

const GAME_STEPS = [
  { n: '01', title: 'A pretend network', body: 'Five fake machines, some reachable from the internet, some holding critical data.' },
  { n: '02', title: 'A simulated attacker', body: 'It sneaks in and tries to reach a critical machine without being stopped.' },
  { n: '03', title: 'A defender choosing moves', body: 'Each step it can watch, slow traffic, cut a machine off, ask for a re-check or call a person.' },
];

function Lab({ data }: { data: BundleResponse }) {
  const { bundle, provenance } = data;
  return (
    <div className="flex flex-col gap-10">
      <section aria-labelledby="lab-what" data-testid="lab-intro">
        <p className="label-mono text-brand">How the game works</p>
        <h2 id="lab-what" className="sr-only">What is this?</h2>
        <p className="mt-2 max-w-3xl text-base text-ink">
          A practice game (a <Term t="simulation">simulation</Term>). An AI defender learned by trial and error a <Term t="policy">policy</Term>:
          which moves keep the intruder out without shutting the business down.
        </p>
        <ol className="mt-5 grid gap-3 md:grid-cols-3">
          {GAME_STEPS.map(step => (
            <li key={step.n} className="rounded-2xl border border-line bg-panel p-5">
              <p className="label-mono text-brand">{step.n}</p>
              <p className="mt-2 font-semibold tracking-tight">{step.title}</p>
              <p className="mt-1 text-sm text-muted">{step.n === '01' ? step.body.replace('Five fake machines', `${machineCountPhrase(bundle.scenarios).replace(/^./, c => c.toUpperCase()).replace(/machines?$/, m => `fake ${m}`)}`) : step.body}</p>
            </li>
          ))}
        </ol>
        <p role="note" className="mt-4 flex items-start gap-2 rounded-xl border border-warn/40 bg-warn/10 px-4 py-3 text-sm text-warn" data-testid="lab-caveat">
          <span aria-hidden="true">⚠</span>
          <span><strong>Simulation only{bundle.simulation_only ? '' : ' (flag missing!)'}.</strong> {bundle.caveat} This is not real network detection and no action is ever applied automatically.</span>
        </p>
      </section>
      <Scoreboard bundle={bundle} />
      <Replay bundle={bundle} />
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

function Scoreboard({ bundle }: { bundle: DefenseLabBundle }) {
  const n = sampleSize(bundle, null);
  const takeaway = keyTakeaway(bundle);
  const tradeoff = tradeoffNote(bundle);
  return (
    <section aria-labelledby="score-title" data-testid="lab-scoreboard">
      <p className="label-mono text-brand">The scores</p>
      <h2 id="score-title" className="mt-2 text-2xl font-semibold tracking-tight md:text-3xl">Who defends best?</h2>
      <p className="mt-2 max-w-3xl text-sm text-muted">
        {defenderCountPhrase(bundle.metrics.length, true)}, each tested on {n.toLocaleString()} games they never trained on. Brackets show the 95% range the true average very likely falls in. ★ marks the best on each measure.
      </p>
      {takeaway && <p className="lab-takeaway mt-5" data-testid="lab-takeaway">{takeaway}</p>}
      <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2">
        {SCORE_METRICS.map(metric => {
          const cells = scoreboard(bundle, metric);
          if (cells.every(c => c.value === null)) return null;
          const fmt = (x: number | null) => (x === null ? '—' : metric.percent ? `${x.toFixed(1)}%` : x.toFixed(1));
          const top = Math.max(...cells.map(x => x.value ?? 0), 1);
          return (
            <figure key={metric.key} className="min-w-0 rounded-2xl border border-line bg-panel p-5" data-testid={`score-${metric.key}`}>
              <figcaption>
                <p className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="font-semibold tracking-tight">{metric.title}</span>
                  <span className="label-mono text-faint">{metric.higherIsBetter ? 'higher is better' : 'lower is better'}</span>
                </p>
                <span className="mt-1 block text-xs text-muted">{metric.explain}</span>
              </figcaption>
              <ul className="mt-4 flex flex-col gap-3">
                {cells.map(c => {
                  const width = c.value === null ? 0 : metric.percent ? Math.min(100, Math.max(0, c.value)) : Math.min(100, (c.value / top) * 100);
                  const ai = c.policy === 'ddqn';
                  return (
                    <li key={c.policy} className="text-sm">
                      <p className="flex items-baseline justify-between gap-2">
                        <span className={ai ? 'font-semibold text-ink' : 'text-muted'} title={POLICY_NAME[c.policy]?.note}>
                          {policyName(c.policy)}{c.best && <span className="lab-best">★ best</span>}
                        </span>
                        <span className="whitespace-nowrap font-mono text-xs">{fmt(c.value)} <span className="text-faint">[{fmt(c.lo)}–{fmt(c.hi)}]</span></span>
                      </p>
                      <span className="mt-1.5 block h-2 overflow-hidden rounded-full bg-panel-2" aria-hidden="true">
                        <span className={`block h-full rounded-full transition-[width] duration-700 ${ai ? 'bg-brand' : 'bg-faint/50'}`} style={{ width: `${width}%` }} />
                      </span>
                    </li>
                  );
                })}
              </ul>
            </figure>
          );
        })}
      </div>
      {tradeoff && <p className="mt-4 flex items-start gap-2 rounded-xl border border-line bg-panel-2 px-4 py-3 text-sm" data-testid="lab-tradeoff"><span aria-hidden="true">⚖</span><span>{tradeoff}</span></p>}
      <ul className="mt-4 grid gap-1.5 text-xs text-muted sm:grid-cols-2">
        {bundle.metrics.map(m => <li key={m.policy}><span className="font-semibold text-ink">{policyName(m.policy)}</span> — {POLICY_NAME[m.policy]?.note ?? 'Policy id from the bundle.'}</li>)}
      </ul>
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
      <p className="label-mono text-brand">Watch a game</p>
      <h2 id="replay-title" className="mt-2 text-2xl font-semibold tracking-tight md:text-3xl">Replay a recorded game</h2>
      <p className="mt-2 max-w-3xl text-sm text-muted">Pick a defender and an attacker, press play, and follow what the defender saw and did at each step.</p>
      {!episode || !scenario ? <div className="mt-4"><Empty>This bundle has no recorded episodes.</Empty></div> : (
        <div className="mt-5 rounded-2xl border border-line bg-panel">
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
          <div className="p-5"><Player key={index} episode={episode} scenario={scenario} /></div>
        </div>
      )}
    </section>
  );
}

const SPEEDS = [{ label: '1×', ms: 160 }, { label: '4×', ms: 40 }] as const;

function Player({ episode, scenario }: { episode: LabEpisode; scenario: LabScenario }) {
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(0);
  const steps = episode.steps.length;
  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => setT(v => { if (v >= steps - 1) { setPlaying(false); return v; } return v + 1; }), SPEEDS[speed]?.ms ?? 160);
    return () => clearInterval(id);
  }, [playing, steps, speed]);

  const step = episode.steps[Math.min(t, steps - 1)];
  const totals = rewardTotals(episode, t + 1);
  const scale = Math.max(0.001, ...Object.values(totals).map(v => Math.abs(v)));
  const seek = (v: number) => { setPlaying(false); setT(v); };
  return (
    <>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-base font-semibold" data-testid="lab-episode-outcome">{episodeOutcome(episode)}</p>
          <p className="mt-0.5 text-xs text-muted" data-testid="lab-episode-story">{SCENARIO_WORDS[episode.scenario]?.note ?? ''} {episodeStory(episode)} {episodeLabel(episode)}.</p>
        </div>
        <span className={`lab-outcome ${episode.compromised ? 'lab-outcome-bad' : 'lab-outcome-ok'}`}>{episode.compromised ? 'Attacker won' : 'Attack contained'}</span>
      </div>
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1.6fr_1fr]">
        <div className="min-w-0">
          <Topology scenario={scenario} states={step?.nodes ?? []} />
          <div className="lab-controls mt-3">
            <Button variant="primary" onClick={() => { if (!playing && t >= steps - 1) setT(0); setPlaying(p => !p); }} aria-pressed={playing}>{playing ? 'Pause' : t >= steps - 1 ? 'Replay' : 'Play'}</Button>
            <div role="group" aria-label="Speed" className="lab-segment lab-segment-sm">
              {SPEEDS.map((sp, i) => <button key={sp.label} type="button" aria-pressed={speed === i} onClick={() => setSpeed(i)} className="lab-segment-btn">{sp.label}</button>)}
            </div>
            <input aria-label="Step" type="range" min={0} max={Math.max(0, steps - 1)} value={t} onChange={e => seek(Number(e.target.value))} className="order-last min-w-0 basis-full accent-[var(--color-brand)] sm:order-none sm:basis-0 sm:flex-1" />
            <span className="font-mono text-xs text-muted">t = {step?.t ?? 0} / {scenario.horizon}</span>
          </div>
          <div className="mt-3"><Timeline episode={episode} t={t} onSeek={seek} /></div>
          <div className="mt-3"><GroundTruth states={step?.nodes ?? []} /></div>
        </div>
        <aside className="flex min-w-0 flex-col gap-3">
          <div className="lab-now">
            <p className="label-mono text-white/60">Step {step?.t ?? 0}</p>
            <p className="mt-2 text-sm text-white/70" data-testid="lab-step-action"><span>At step {step?.t ?? 0} the defender: </span><strong className="block text-lg text-white">{step ? actionInWords(step.action) : '—'}</strong></p>
            <p className="mt-3 text-sm text-white/75" data-testid="lab-step-story">{stepObservation(step)}</p>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-xl border border-line px-3 py-2.5"><p className="label-mono text-faint">This step</p><p className={`mt-1 font-display text-xl font-semibold ${(step?.reward ?? 0) < 0 ? 'text-bad' : 'text-ink'}`}>{num(step?.reward ?? 0, 3)}</p></div>
            <div className="rounded-xl border border-line px-3 py-2.5"><p className="label-mono text-faint">Score so far</p><p className="mt-1 font-display text-xl font-semibold">{num(cumulativeReturn(episode, t + 1), 2)}</p><p className="text-xs text-faint">final {num(episode.total_return, 2)}</p></div>
          </div>
          <div className="rounded-xl border border-line p-3">
            <p className="mb-2 text-xs font-semibold text-muted">Where the score comes from <span className="font-normal text-faint">(red = cost to the defender)</span></p>
            <ul className="flex flex-col gap-1.5 text-xs">
              {Object.entries(totals).map(([k, v]) => (
                <li key={k} className="grid grid-cols-[minmax(0,1fr)_4.5rem_3.5rem] items-center gap-2" title={k}>
                  <span className="truncate">{rewardWord(k)}</span>
                  <span className="lab-diverge" aria-hidden="true"><span className={v < 0 ? 'lab-diverge-neg' : 'lab-diverge-pos'} style={{ width: `${(Math.abs(v) / scale) * 50}%` }} /></span>
                  <span className={`text-right font-mono ${v < 0 ? 'text-bad' : v > 0 ? 'text-ok' : 'text-faint'}`}>{num(v, 2)}</span>
                </li>
              ))}
            </ul>
          </div>
        </aside>
      </div>
    </>
  );
}

const STAGE_TONE = { none: 'neutral', foothold: 'warn', escalated: 'bad', impact: 'bad' } as const;

function GroundTruth({ states }: { states: LabNodeState[] }) {
  return (
    <div className="rounded-xl border border-line px-3 py-2 text-xs">
        <p className="mb-1.5 font-semibold text-muted">Ground truth (simulation) — hidden attacker stage, never observed by the policy</p>
        <div className="flex flex-wrap gap-1.5">
          {states.map(s => <span key={s.node} className="flex items-center gap-1"><Mono>{s.node}</Mono><Badge view={{ label: s.hidden_stage_ground_truth, tone: STAGE_TONE[s.hidden_stage_ground_truth], glyph: s.hidden_stage_ground_truth === 'none' ? '·' : '!' }} /></span>)}
        </div>
        <p className="mt-1.5 text-faint">The defender only sees alert rate, anomaly score, monitoring level and its own actions. <Tag>simulator replay</Tag></p>
      </div>
  );
}

function Topology({ scenario, states }: { scenario: LabScenario; states: LabNodeState[] }) {
  return (
    <figure>
      <NodeGraph scenario={scenario} states={states} />
      <details className="lab-legend mt-2 text-xs text-muted">
        <summary className="cursor-pointer select-none">How to read the map</summary>
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
          <span className="flex items-center gap-1.5"><span className="graph-key bg-brand" />Glow and colour = anomaly score (observed)</span>
          <span className="flex items-center gap-1.5"><span className="graph-key border border-brand" />Ring = internet-exposed</span>
          <span className="flex items-center gap-1.5"><span className="graph-key border-2 border-warn" />Amber ring = isolated</span>
          <span className="flex items-center gap-1.5"><span className="graph-key-line" />Dashed link = rate-limited or hot</span>
          <span>Size = criticality · hover to inspect · drag to rearrange</span>
        </div>
      </details>
    </figure>
  );
}

const STAGE_FILL = { none: 'transparent', foothold: 'var(--color-warn)', escalated: 'color-mix(in srgb, var(--color-bad) 65%, white)', impact: 'var(--color-bad)' } as const;

/** Whole game at a glance: hidden attacker progress (ground truth) above, defender actions below. */
function Timeline({ episode, t, onSeek }: { episode: LabEpisode; t: number; onSeek: (t: number) => void }) {
  const rows = useMemo(() => episodeTimeline(episode), [episode]);
  const w = Math.max(1, rows.length);
  return (
    <figure data-testid="lab-timeline">
      <svg viewBox={`0 0 ${w} 22`} preserveAspectRatio="none" className="h-14 w-full cursor-pointer rounded border border-line bg-bg" role="img"
        aria-label={`Game timeline over ${rows.length} steps: attacker progress and defender actions`}
        onClick={e => { const r = (e.currentTarget as SVGSVGElement).getBoundingClientRect(); onSeek(Math.min(rows.length - 1, Math.max(0, Math.floor(((e.clientX - r.left) / r.width) * rows.length)))); }}>
        {rows.map((r, i) => (
          <g key={i}>
            <rect x={i} y={1} width={1.02} height={9} fill={STAGE_FILL[r.stage]} />
            {r.acted && <rect x={i} y={13} width={1.02} height={8} fill={r.disruptive ? 'var(--color-brand)' : 'color-mix(in srgb, var(--color-brand) 35%, white)'} />}
          </g>
        ))}
        <line x1={t + 0.5} x2={t + 0.5} y1={0} y2={22} stroke="var(--color-ink)" strokeWidth={Math.max(0.6, w / 300)} vectorEffect="non-scaling-stroke" />
      </svg>
      <figcaption className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
        <span><strong>Top:</strong> how far the hidden attacker got (simulation ground truth, never shown to the defender):
          {' '}<Swatch c={STAGE_FILL.foothold} /> {STAGE_WORDS.foothold} <Swatch c={STAGE_FILL.escalated} /> {STAGE_WORDS.escalated} <Swatch c={STAGE_FILL.impact} /> {STAGE_WORDS.impact}</span>
        <span><strong>Bottom:</strong> <Swatch c="var(--color-brand)" /> disruptive action (cut off / slow down) <Swatch c="color-mix(in srgb, var(--color-brand) 35%, white)" /> other action. Click to jump, or use the Step slider.</span>
      </figcaption>
    </figure>
  );
}

function Swatch({ c }: { c: string }) {
  return <span aria-hidden="true" className="inline-block h-2.5 w-2.5 rounded-sm align-middle" style={{ background: c }} />;
}
