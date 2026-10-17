'use client';

import { useEffect, useMemo, useState } from 'react';
import { Badge, Button, Empty, ErrorState, Field, inputClass, Loading, Mono, PageTitle, Panel, Stat, Tag } from '@/components/ui';
import { num } from '@/lib/format';
import { cumulativeReturn, domain, episodeLabel, episodeStory, HIGHER_IS_BETTER, METRIC_LABEL, metricNames, metricRows, rewardTotals, sampleSize, stepObservation } from '@/lib/lab';
import { actionInWords, episodeOutcome, episodeTimeline, POLICY_NAME, policyName, SCORE_METRICS, scoreboard, STAGE_WORDS, tradeoffNote } from '@/lib/lab-plain';
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
      <PageTitle
        title="Defense Lab"
        subtitle="A Double DQN defender trained and evaluated in a simulated network. Separate from the security agents: research and decision support, never production control."
        actions={protocols.status === 'ready' && protocols.data.length > 0 && (
          <Field label="Evaluation run">
            <select className={inputClass} value={protocol} onChange={e => setProtocol(e.target.value)} name="protocol">
              {protocols.data.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
          </Field>
        )}
      />
      {protocols.status === 'loading' && <Loading label="Finding evaluation runs" />}
      {protocols.status === 'error' && <ErrorState error={protocols.error} context="Could not list evaluation runs" />}
      {protocols.status === 'ready' && protocols.data.length === 0 && <Empty>No committed evaluation bundle (rl-defense/results/protocol-*/defense_lab.json) was found.</Empty>}
      {protocol && bundle.status === 'loading' && <Loading label={`Loading ${protocol}`} />}
      {bundle.status === 'error' && <ErrorState error={bundle.error} context="Evaluation bundle rejected" />}
      {bundle.status === 'ready' && <Lab data={bundle.data} />}
    </>
  );
}

function Lab({ data }: { data: BundleResponse }) {
  const { bundle, provenance } = data;
  return (
    <div className="flex flex-col gap-4">
      <section aria-labelledby="lab-what" className="rounded-xl border border-line bg-panel p-5" data-testid="lab-intro">
        <h2 id="lab-what" className="text-lg font-semibold tracking-tight">What is this?</h2>
        <p className="mt-1 max-w-3xl text-sm text-ink">
          A practice game. A pretend company network of five machines is attacked by a simulated intruder, and an AI defender
          learned by trial and error which actions keep the intruder out without shutting the business down. Below you can see
          how it scores against simpler defenders, and replay a recorded game step by step.
        </p>
        <div role="note" className="mt-3 rounded-md border border-warn/50 bg-warn/10 px-3 py-2 text-sm text-warn" data-testid="lab-caveat">
          <strong>Simulation only{bundle.simulation_only ? '' : ' (flag missing!)'}.</strong> {bundle.caveat} This is not real network detection and no action is ever applied automatically.
        </div>
      </section>
      <Scoreboard bundle={bundle} />
      <Replay bundle={bundle} />
      <details className="group rounded-xl border border-line bg-panel" data-testid="lab-details">
        <summary className="cursor-pointer list-none px-4 py-3 text-sm font-semibold">
          <span aria-hidden="true" className="mr-1 inline-block transition-transform group-open:rotate-90">▸</span>
          For reviewers: every metric, per scenario, and where these numbers come from
        </summary>
        <div className="flex flex-col gap-4 border-t border-line p-4">
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
  return (
    <section aria-labelledby="score-title" className="rounded-xl border border-line bg-panel p-5" data-testid="lab-scoreboard">
      <h2 id="score-title" className="text-lg font-semibold tracking-tight">Who defends best?</h2>
      <p className="mt-1 text-sm text-muted">
        Four defenders, each tested on {n.toLocaleString()} games they never trained on. The range in brackets is the 95% confidence interval:
        the true average very likely lies inside it. ★ marks the best of the four on that measure.
      </p>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        {SCORE_METRICS.map(metric => {
          const cells = scoreboard(bundle, metric);
          if (cells.every(c => c.value === null)) return null;
          const fmt = (x: number | null) => (x === null ? '—' : metric.percent ? `${x.toFixed(1)}%` : x.toFixed(1));
          return (
            <figure key={metric.key} className="min-w-0 rounded-lg border border-line p-3" data-testid={`score-${metric.key}`}>
              <figcaption>
                <span className="font-semibold">{metric.title}</span>
                <span className="ml-2 text-xs text-faint">{metric.higherIsBetter ? 'higher is better' : 'lower is better'}</span>
                <span className="mt-0.5 block text-xs text-muted">{metric.explain}</span>
              </figcaption>
              <ul className="mt-2 flex flex-col gap-1.5">
                {cells.map(c => {
                  const width = c.value === null ? 0 : metric.percent ? Math.min(100, Math.max(0, c.value)) : Math.min(100, (c.value / Math.max(...cells.map(x => x.value ?? 0), 1)) * 100);
                  return (
                    <li key={c.policy} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-2 gap-y-1 text-sm sm:grid-cols-[9.5rem_minmax(0,1fr)_auto]">
                      <span className={c.policy === 'ddqn' ? 'font-semibold' : ''} title={POLICY_NAME[c.policy]?.note}>{policyName(c.policy)}</span>
                      <span className="order-last col-span-2 h-2.5 overflow-hidden rounded-full bg-panel-2 sm:order-none sm:col-span-1" aria-hidden="true">
                        <span className={`block h-full rounded-full ${c.policy === 'ddqn' ? 'bg-brand' : 'bg-faint/60'}`} style={{ width: `${width}%` }} />
                      </span>
                      <span className="whitespace-nowrap font-mono text-xs">
                        {c.best && <span aria-label="best">★ </span>}{fmt(c.value)} <span className="text-faint">[{fmt(c.lo)}–{fmt(c.hi)}]</span>
                      </span>
                    </li>
                  );
                })}
              </ul>
            </figure>
          );
        })}
      </div>
      {tradeoffNote(bundle) && <p className="mt-3 rounded-md border border-warn/40 bg-warn/10 px-3 py-2 text-sm" data-testid="lab-tradeoff">{tradeoffNote(bundle)}</p>}
      <ul className="mt-3 grid gap-1 text-xs text-muted sm:grid-cols-2">
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
            <span className={r.policy === 'ddqn' ? 'font-semibold text-accent' : 'text-muted'}>{r.policy}</span>
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
  const [index, setIndex] = useState(0);
  const episode: LabEpisode | undefined = bundle.episodes[index];
  const scenario = bundle.scenarios.find(s => s.name === episode?.scenario);
  if (!episode || !scenario) return <Panel title="Episode replay"><Empty>This bundle has no recorded episodes.</Empty></Panel>;
  return (
    <Panel title="Replay a recorded game" actions={
      <select aria-label="Episode" className={inputClass} value={index} onChange={e => setIndex(Number(e.target.value))}>
        {bundle.episodes.map((e, i) => <option key={i} value={i}>{policyName(e.policy)} · {e.scenario.replace(/^eval_/, '').replaceAll('_', ' ')} · game {e.episode_seed}</option>)}
      </select>
    }>
      <Player key={index} episode={episode} scenario={scenario} />
    </Panel>
  );
}

function Player({ episode, scenario }: { episode: LabEpisode; scenario: LabScenario }) {
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const steps = episode.steps.length;
  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => setT(v => { if (v >= steps - 1) { setPlaying(false); return v; } return v + 1; }), 120);
    return () => clearInterval(id);
  }, [playing, steps]);

  const step = episode.steps[Math.min(t, steps - 1)];
  const totals = rewardTotals(episode, t + 1);
  return (
    <>
      <p className="mb-1 text-base font-semibold" data-testid="lab-episode-outcome">{episodeOutcome(episode)}</p>
      <p className="mb-3 text-xs text-muted" data-testid="lab-episode-story">{episodeStory(episode)} {episodeLabel(episode)}.</p>
      <Timeline episode={episode} t={t} onSeek={v => { setPlaying(false); setT(v); }} />
      <p className="mb-1 mt-3 text-sm" data-testid="lab-step-action"><span className="text-faint">At step {step?.t ?? 0} the defender: </span><strong>{step ? actionInWords(step.action) : '—'}</strong></p>
      <p className="mb-3 text-sm text-ink" data-testid="lab-step-story">{stepObservation(step)}</p>
      <div className="grid gap-4 lg:grid-cols-[3fr_2fr]">
        <div>
          <Topology scenario={scenario} states={step?.nodes ?? []} />
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button onClick={() => setPlaying(p => !p)} aria-pressed={playing}>{playing ? 'Pause' : 'Play'}</Button>
            <input aria-label="Step" type="range" min={0} max={Math.max(0, steps - 1)} value={t} onChange={e => { setPlaying(false); setT(Number(e.target.value)); }} className="flex-1 accent-[var(--color-accent)]" />
            <span className="font-mono text-xs text-muted">t = {step?.t ?? 0} / {scenario.horizon}</span>
          </div>
        </div>
        <div className="flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-2">
            <Stat label="Action at t" value={<span className="text-sm">{step ? actionInWords(step.action) : '—'}</span>} hint={step?.action} />
            <Stat label="Step reward" value={num(step?.reward ?? 0, 3)} />
            <Stat label="Return so far" value={num(cumulativeReturn(episode, t + 1), 2)} hint={`episode total ${num(episode.total_return, 2)}`} />
            <Stat label="Outcome" value={<span className="text-sm">{episode.compromised ? 'compromised' : 'contained'}</span>} hint={episode.impact_nodes.length ? `impact: ${episode.impact_nodes.join(', ')}` : undefined} />
          </div>
          <div>
            <p className="mb-1 text-xs font-semibold text-muted">Score so far, broken into its 8 parts (negative = cost to the defender)</p>
            <ul className="flex flex-col gap-0.5 text-xs">
              {Object.entries(totals).map(([k, v]) => (
                <li key={k} className="flex justify-between"><Mono>{k}</Mono><span className={`font-mono ${v < 0 ? 'text-bad' : v > 0 ? 'text-ok' : 'text-faint'}`}>{num(v, 3)}</span></li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </>
  );
}

const STAGE_TONE = { none: 'neutral', foothold: 'warn', escalated: 'bad', impact: 'bad' } as const;

/** Layered layout: exposed nodes first, then breadth-first along edges. */
function layout(s: LabScenario): Map<string, { x: number; y: number }> {
  const depth = new Map<string, number>();
  const queue = s.nodes.filter(n => n.exposed).map(n => n.name);
  queue.forEach(q => depth.set(q, 0));
  while (queue.length) {
    const cur = queue.shift() as string;
    for (const [a, b] of s.edges) {
      const next = a === cur ? b : null;
      if (next && !depth.has(next)) { depth.set(next, (depth.get(cur) ?? 0) + 1); queue.push(next); }
    }
  }
  s.nodes.forEach(n => { if (!depth.has(n.name)) depth.set(n.name, 0); });
  const layers = new Map<number, string[]>();
  for (const [name, d] of depth) layers.set(d, [...(layers.get(d) ?? []), name]);
  const maxD = Math.max(...layers.keys());
  const pos = new Map<string, { x: number; y: number }>();
  for (const [d, names] of layers) names.forEach((name, i) => pos.set(name, { x: 60 + (d * 480) / Math.max(1, maxD), y: ((i + 1) * 220) / (names.length + 1) }));
  return pos;
}

function Topology({ scenario, states }: { scenario: LabScenario; states: LabNodeState[] }) {
  const pos = useMemo(() => layout(scenario), [scenario]);
  const state = new Map(states.map(s => [s.node, s]));
  return (
    <figure>
      <svg viewBox="0 0 600 220" className="w-full rounded border border-line bg-bg" role="img" aria-label={`Simulated topology for ${scenario.name}`} data-testid="topology">
        {scenario.edges.map(([a, b]) => {
          const p = pos.get(a); const q = pos.get(b);
          return p && q ? <line key={a + b} x1={p.x} y1={p.y} x2={q.x} y2={q.y} stroke="var(--color-line)" strokeWidth={2} /> : null;
        })}
        {scenario.nodes.map(n => {
          const p = pos.get(n.name);
          const s = state.get(n.name);
          if (!p) return null;
          const heat = Math.min(1, s?.anomaly_score ?? 0);
          return (
            <g key={n.name} transform={`translate(${p.x},${p.y})`}>
              <circle r={22} fill={`color-mix(in srgb, var(--color-bad) ${Math.round(heat * 70)}%, var(--color-panel-2))`} stroke={s?.isolated ? 'var(--color-warn)' : n.exposed ? 'var(--color-accent)' : 'var(--color-line)'} strokeWidth={s?.isolated ? 3 : 1.5} strokeDasharray={s?.rate_limited ? '4 3' : undefined} />
              <text textAnchor="middle" y={4} fontSize={11} fill="var(--color-ink)">{n.name}</text>
              <text textAnchor="middle" y={38} fontSize={9} fill="var(--color-muted)">crit {n.criticality} · anomaly {num(s?.anomaly_score ?? 0, 2)}</text>
            </g>
          );
        })}
      </svg>
      <figcaption className="mt-2 flex flex-wrap gap-2 text-xs text-muted">
        <span>Fill = anomaly score (observed).</span><span>Brand-red ring = internet-exposed.</span><span>Thick amber ring = isolated.</span><span>Dashed = rate-limited.</span>
      </figcaption>
      <div className="mt-2 rounded border border-line p-2 text-xs">
        <p className="mb-1 font-semibold text-muted">Ground truth (simulation) — hidden attacker stage, never observed by the policy</p>
        <div className="flex flex-wrap gap-1.5">
          {states.map(s => <span key={s.node} className="flex items-center gap-1"><Mono>{s.node}</Mono><Badge view={{ label: s.hidden_stage_ground_truth, tone: STAGE_TONE[s.hidden_stage_ground_truth], glyph: s.hidden_stage_ground_truth === 'none' ? '·' : '!' }} /></span>)}
        </div>
        <p className="mt-1 text-faint">Observed per-node: alert rate, anomaly score, monitoring level, rate-limited, isolated, reassessment pending. <Tag>simulator replay</Tag></p>
      </div>
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
        <span><strong>Bottom:</strong> <Swatch c="var(--color-brand)" /> disruptive action (cut off / slow down) <Swatch c="color-mix(in srgb, var(--color-brand) 35%, white)" /> other action. Click to jump.</span>
      </figcaption>
    </figure>
  );
}

function Swatch({ c }: { c: string }) {
  return <span aria-hidden="true" className="inline-block h-2.5 w-2.5 rounded-sm align-middle" style={{ background: c }} />;
}
