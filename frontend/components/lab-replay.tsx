'use client';

import { useEffect, useMemo, useState } from 'react';
import { NodeGraph, StateBadge } from '@/components/node-graph';
import { Mono } from '@/components/ui';
import { num } from '@/lib/format';
import { cumulativeReturn, episodeLabel, episodeStory, rewardTotals, stepObservation } from '@/lib/lab';
import { actionInWords, episodeOutcome, rewardWord, SCENARIO_WORDS, STAGE_WORDS } from '@/lib/lab-plain';
import {
  ACTION_SHORT, actionMeaning, isDisruptive, keyMoments, latestAction, nodeStatusLine, nodeViews, overallStatus, parseAction,
  serviceInfo, signalValue, SIGNAL_BANDS, SIGNAL_WORDS, stepStory, storyMoments, type Moment,
} from '@/lib/lab-story';
import type { HiddenStage, LabEpisode, LabScenario } from '@/lib/lab-types';

const SPEEDS = [{ label: '1×', ms: 180 }, { label: '4×', ms: 45 }, { label: '8×', ms: 22 }] as const;

/** Recorded-episode player: status, network map, story panel, and playback timeline. */
export function ReplayStage({ episode, scenario }: { episode: LabEpisode; scenario: LabScenario }) {
  const steps = episode.steps.length;
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [truth, setTruth] = useState(false);
  const moments = useMemo(() => keyMoments(episode, scenario), [episode, scenario]);
  const story = useMemo(() => storyMoments(moments), [moments]);

  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => setT(v => { if (v >= steps - 1) { setPlaying(false); return v; } return v + 1; }), SPEEDS[speed]?.ms ?? 180);
    return () => clearInterval(id);
  }, [playing, steps, speed]);

  const step = episode.steps[Math.min(t, steps - 1)];
  const seek = (v: number) => { setPlaying(false); setT(Math.max(0, Math.min(steps - 1, v))); };
  const nextMoment = moments.find(m => m.t > t);
  const prevMoment = [...moments].reverse().find(m => m.t < t);
  const status = overallStatus(scenario, step);
  const last = latestAction(episode, t);
  const s = stepStory(episode, scenario, t);
  const label = (n: string) => serviceInfo(n).label;

  return (
    <div className="flex flex-col gap-4">
      {/* Status overview */}
      <div className="lab-status" data-testid="lab-status">
        <span className="lab-mode label-mono" data-testid="lab-mode">Simulation · recorded evaluation</span>
        <span className="lab-status-item"><span className="text-faint">Attacker</span> {SCENARIO_WORDS[episode.scenario]?.name ?? episode.scenario}</span>
        <span className="lab-status-item"><span className="text-faint">Watching</span> {scenario.nodes.length} services</span>
        <span className={`lab-status-item lab-tone-${status.tone}`}><span aria-hidden="true" className="lab-dot" />{status.text}</span>
        <span className="lab-status-item min-w-0"><span className="text-faint">Latest AI action</span> <span className="truncate">{last ? `${actionInWords(last.action)} (step ${last.t})` : 'none yet'}</span></span>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.75fr)_minmax(19rem,1fr)]">
        <div className="min-w-0">
          <NodeGraph scenario={scenario} states={step?.nodes ?? []} action={step?.action} t={t} selected={selected} onSelect={setSelected} showTruth={truth} />
          <Legend />
        </div>

        <aside className="flex min-w-0 flex-col gap-3" aria-label="What's happening">
          <div className="lab-now">
            <p className="label-mono flex justify-between text-white/60"><span>Step {step?.t ?? 0} of {scenario.horizon}</span><span>Recorded</span></p>
            <dl className="mt-3 flex flex-col gap-3 text-sm">
              <div><dt className="lab-q">What’s happening</dt><dd className="text-white/85" data-testid="lab-step-story">{s.now}</dd></div>
              <div>
                <dt className="lab-q">What the AI did</dt>
                <dd data-testid="lab-step-action"><span className="sr-only">At step {step?.t ?? 0} the defender: </span><strong className="block text-white">{s.did}</strong>{s.tradeoff && <span className="mt-1 block text-white/60">{s.tradeoff}</span>}</dd>
              </div>
              <div><dt className="lab-q">Why</dt><dd className="text-white/70">{s.why}</dd></div>
              {s.effect && <div><dt className="lab-q">Did it change anything?</dt><dd className="text-white/85" data-testid="lab-step-effect">{s.effect}</dd></div>}
              <div><dt className="lab-q">Cost</dt><dd className="text-white/70">{s.cost}</dd></div>
            </dl>
          </div>
          {selected ? <ServicePanel episode={episode} scenario={scenario} name={selected} t={t} truth={truth} onClose={() => setSelected(null)} /> : (
            <p className="rounded-xl border border-dashed border-line px-4 py-3 text-sm text-muted">Select a service on the map to see what it does and what the AI saw there.</p>
          )}
          <details className="rounded-xl border border-line px-4 py-3 text-xs">
            <summary className="cursor-pointer font-semibold text-muted">Technical details for this step</summary>
            <p className="mt-2 text-muted">{stepObservation(step)}</p>
            <p className="mt-2">Raw action: <Mono>{step?.action ?? '—'}</Mono> · step reward <Mono>{num(step?.reward ?? 0, 3)}</Mono> · score so far <Mono>{num(cumulativeReturn(episode, t + 1), 2)}</Mono> (final {num(episode.total_return, 2)})</p>
            <ScoreParts episode={episode} t={t} />
          </details>
        </aside>
      </div>

      {/* Playback */}
      <div className="lab-player">
        <div className="lab-controls">
          <button type="button" className="lab-ctl" onClick={() => prevMoment && seek(prevMoment.t)} disabled={!prevMoment} aria-label="Previous key moment">⏮</button>
          <button type="button" className="lab-ctl lab-ctl-main" onClick={() => { if (!playing && t >= steps - 1) setT(0); setPlaying(p => !p); }} aria-pressed={playing}>{playing ? 'Pause' : t >= steps - 1 ? 'Replay' : 'Play'}</button>
          <button type="button" className="lab-ctl" onClick={() => nextMoment && seek(nextMoment.t)} disabled={!nextMoment} aria-label="Next key moment">⏭</button>
          <div role="group" aria-label="Speed" className="lab-segment lab-segment-sm">
            {SPEEDS.map((sp, i) => <button key={sp.label} type="button" aria-pressed={speed === i} onClick={() => setSpeed(i)} className="lab-segment-btn">{sp.label}</button>)}
          </div>
          <input aria-label="Step" type="range" min={0} max={Math.max(0, steps - 1)} value={t} onChange={e => seek(Number(e.target.value))} className="order-last min-w-0 basis-full accent-[var(--color-brand)] sm:order-none sm:basis-0 sm:flex-1" />
          <span className="font-mono text-xs text-muted">t = {step?.t ?? 0} / {scenario.horizon}</span>
        </div>
        <Timeline episode={episode} moments={moments} t={t} onSeek={seek} truth={truth} />
        <ol className="lab-moments" aria-label="Key moments">
          {story.map(m => (
            <li key={`${m.t}-${m.kind}-${m.text}`}>
              <button type="button" onClick={() => seek(m.t)} className="lab-moment" data-kind={m.kind} aria-current={m.t === t ? 'step' : undefined}>
                <span className="font-mono text-faint">{m.t}</span>{m.text}
              </button>
            </li>
          ))}
        </ol>
      </div>

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-base font-semibold" data-testid="lab-episode-outcome">{episodeOutcome(episode)}</p>
          <p className="mt-0.5 max-w-3xl text-xs text-muted" data-testid="lab-episode-story">{SCENARIO_WORDS[episode.scenario]?.note ?? ''} {episodeStory(episode)} {episodeLabel(episode)}.</p>
        </div>
        <span className={`lab-outcome ${episode.compromised ? 'lab-outcome-bad' : 'lab-outcome-ok'}`}>{episode.compromised ? 'Attacker won' : 'Attack contained'}</span>
      </div>

      <GroundTruth episode={episode} t={t} truth={truth} onToggle={setTruth} label={label} />
    </div>
  );
}

function Legend() {
  return (
    <div className="lab-legend" aria-label="Map legend">
      <span><svg viewBox="-12 -12 24 24" className="lab-key"><circle r="8" className="lk-quiet" /></svg>{SIGNAL_WORDS.quiet}</span>
      <span><svg viewBox="-12 -12 24 24" className="lab-key"><circle r="8" className="lk-elevated" /></svg>{SIGNAL_WORDS.elevated}</span>
      <span><svg viewBox="-12 -12 24 24" className="lab-key"><circle r="8" className="lk-high" /></svg>{SIGNAL_WORDS.high}</span>
      <span><svg viewBox="-12 -12 24 24" className="lab-key lab-key-dark"><StateBadge kind="watch" /></svg>Watched closely</span>
      <span><svg viewBox="-12 -12 24 24" className="lab-key lab-key-dark"><StateBadge kind="slow" /></svg>Traffic slowed</span>
      <span><svg viewBox="-12 -12 24 24" className="lab-key lab-key-dark"><StateBadge kind="cut" /></svg>Cut off</span>
      <span><svg viewBox="-12 -12 24 24" className="lab-key lab-key-dark"><StateBadge kind="recheck" /></svg>Re-check requested</span>
      <span className="text-faint">Bigger = more critical. Signal bands: elevated ≥ {SIGNAL_BANDS.elevated}, suspicious ≥ {SIGNAL_BANDS.high} (alert rate or anomaly score).</span>
    </div>
  );
}

function ServicePanel({ episode, scenario, name, t, truth, onClose }: { episode: LabEpisode; scenario: LabScenario; name: string; t: number; truth: boolean; onClose: () => void }) {
  const step = episode.steps[t];
  const view = nodeViews(scenario, step?.nodes ?? []).find(v => v.name === name);
  const state = step?.nodes.find(n => n.node === name);
  const info = serviceInfo(name);
  const history = episode.steps.slice(0, t + 1).map(s => signalValue(s.nodes.find(n => n.node === name)) ?? 0);
  const actions = episode.steps.slice(0, t + 1).map((s, i) => ({ t: s.t ?? i, ...parseAction(s.action) })).filter(a => a.node === name);
  const lastAct = actions.at(-1);
  if (!view) return null;
  const w = 240; const h = 40;
  const pts = history.map((v, i) => `${(i / Math.max(1, episode.steps.length - 1)) * w},${h - v * h}`).join(' ');
  return (
    <section className="rounded-xl border border-line bg-panel p-4" aria-labelledby="svc-title" data-testid="lab-service-panel">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="label-mono text-faint">{name}{view.critical ? ' · critical' : ''}</p>
          <h3 id="svc-title" className="mt-1 text-lg font-semibold tracking-tight">{info.label}</h3>
        </div>
        <button type="button" onClick={onClose} className="rounded-md px-2 py-1 text-xs text-muted hover:bg-panel-2" aria-label="Close service details">Close</button>
      </div>
      <p className="mt-1 text-sm text-muted">{info.role}</p>
      <ul className="mt-3 flex flex-col gap-1.5 text-sm">
        <li><span className="text-faint">Reachable from the internet: </span>{view.exposed ? 'yes' : 'no'}</li>
        <li><span className="text-faint">Right now: </span>{nodeStatusLine(view)}</li>
        <li><span className="text-faint">AI actions here so far: </span>{actions.length === 0 ? 'none' : `${actions.length} (latest at step ${lastAct?.t}: ${ACTION_SHORT[lastAct?.verb ?? ''] ?? lastAct?.verb})`}</li>
      </ul>
      {lastAct && <p className="mt-2 text-xs text-muted">{actionMeaning(`${lastAct.verb}:${name}`, () => info.label).did}</p>}
      <figure className="mt-3">
        <svg viewBox={`0 0 ${w} ${h}`} className="h-10 w-full overflow-visible" role="img" aria-label={`Signal at ${info.label} from step 0 to ${t}`}>
          <line x1="0" x2={w} y1={h - SIGNAL_BANDS.high * h} y2={h - SIGNAL_BANDS.high * h} stroke="var(--color-line)" strokeDasharray="3 3" />
          <polyline points={pts} fill="none" stroke="var(--color-brand)" strokeWidth="1.6" vectorEffect="non-scaling-stroke" />
        </svg>
        <figcaption className="text-xs text-faint">Observed signal so far (dashed line = suspicious band)</figcaption>
      </figure>
      {truth && state && <p className="mt-2 text-xs text-[#b42318]">Hidden truth (not seen by the defender): attacker {STAGE_WORDS[state.hidden_stage_ground_truth]}.</p>}
      <details className="mt-3 text-xs">
        <summary className="cursor-pointer text-muted">Observed values</summary>
        <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1">
          <dt className="text-faint">alert rate</dt><dd className="font-mono">{num(state?.alert_rate ?? 0, 2)}</dd>
          <dt className="text-faint">anomaly score</dt><dd className="font-mono">{num(state?.anomaly_score ?? 0, 2)}</dd>
          <dt className="text-faint">monitoring level</dt><dd className="font-mono">{state?.monitoring_level ?? 0}</dd>
          <dt className="text-faint">rate limited</dt><dd className="font-mono">{String(!!state?.rate_limited)}</dd>
          <dt className="text-faint">isolated</dt><dd className="font-mono">{String(!!state?.isolated)}</dd>
          <dt className="text-faint">reassessment pending</dt><dd className="font-mono">{String(!!state?.reassessment_pending)}</dd>
        </dl>
      </details>
    </section>
  );
}

function ScoreParts({ episode, t }: { episode: LabEpisode; t: number }) {
  const totals = rewardTotals(episode, t + 1);
  const scale = Math.max(0.001, ...Object.values(totals).map(v => Math.abs(v)));
  return (
    <ul className="mt-3 flex flex-col gap-1.5">
      {Object.entries(totals).map(([k, v]) => (
        <li key={k} className="grid grid-cols-[minmax(0,1fr)_4.5rem_3.5rem] items-center gap-2" title={k}>
          <span className="truncate">{rewardWord(k)}</span>
          <span className="lab-diverge" aria-hidden="true"><span className={v < 0 ? 'lab-diverge-neg' : 'lab-diverge-pos'} style={{ width: `${(Math.abs(v) / scale) * 50}%` }} /></span>
          <span className={`text-right font-mono ${v < 0 ? 'text-bad' : v > 0 ? 'text-ok' : 'text-faint'}`}>{num(v, 2)}</span>
        </li>
      ))}
    </ul>
  );
}

const STAGE_FILL: Record<HiddenStage, string> = { none: 'transparent', foothold: '#f0a868', escalated: '#e0735c', impact: '#b42318' };
const STAGE_RANK: Record<HiddenStage, number> = { none: 0, foothold: 1, escalated: 2, impact: 3 };

/** Whole recording at a glance: observed signal strip, AI actions, key moments; truth row only on request. */
function Timeline({ episode, moments, t, onSeek, truth }: { episode: LabEpisode; moments: Moment[]; t: number; onSeek: (t: number) => void; truth: boolean }) {
  const n = Math.max(1, episode.steps.length);
  const rows = useMemo(() => episode.steps.map(s => {
    const peak = Math.max(0, ...s.nodes.map(x => signalValue(x) ?? 0));
    let stage: HiddenStage = 'none';
    for (const x of s.nodes) if (STAGE_RANK[x.hidden_stage_ground_truth] > STAGE_RANK[stage]) stage = x.hidden_stage_ground_truth;
    const a = parseAction(s.action);
    return { peak, stage, acted: a.verb !== 'noop', disruptive: isDisruptive(a.verb) };
  }), [episode]);
  const H = truth ? 34 : 26;
  return (
    <figure data-testid="lab-timeline">
      <svg viewBox={`0 0 ${n} ${H}`} preserveAspectRatio="none" className="h-16 w-full cursor-pointer rounded-lg bg-panel-2" role="img"
        aria-label={`Timeline of ${n} steps: observed signal, AI actions and key moments`}
        onClick={e => { const r = (e.currentTarget as SVGSVGElement).getBoundingClientRect(); onSeek(Math.floor(((e.clientX - r.left) / r.width) * n)); }}>
        {rows.map((r, i) => (
          <g key={i}>
            <rect x={i} y={2} width={1.02} height={9} fill="#c2452d" opacity={0.08 + r.peak * 0.8} />
            {r.acted && <rect x={i} y={13} width={1.02} height={7} fill={r.disruptive ? '#1c1210' : '#9a857f'} />}
            {truth && <rect x={i} y={26} width={1.02} height={6} fill={STAGE_FILL[r.stage]} />}
          </g>
        ))}
        {moments.filter(m => m.kind === 'signal').map(m => <rect key={`m${m.t}${m.node}`} x={m.t} y={0} width={Math.max(0.6, n / 300)} height={H} fill="#c2452d" opacity={0.5} />)}
        <line x1={t + 0.5} x2={t + 0.5} y1={0} y2={H} stroke="var(--color-ink)" strokeWidth={2} vectorEffect="non-scaling-stroke" />
      </svg>
      <figcaption className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
        <span><Swatch c="#c2452d" o={0.7} /> Top: strongest observed signal at each step</span>
        <span><Swatch c="#1c1210" /> disruptive AI action (slow / cut off) <Swatch c="#9a857f" /> other AI action</span>
        <span><Swatch c="#c2452d" o={0.5} w /> moment a service turned suspicious</span>
        {truth && <span><Swatch c={STAGE_FILL.foothold} /> <Swatch c={STAGE_FILL.escalated} /> <Swatch c={STAGE_FILL.impact} /> hidden attacker progress (truth, not seen by the defender)</span>}
        <span>Click to jump.</span>
      </figcaption>
    </figure>
  );
}

function Swatch({ c, o = 1, w = false }: { c: string; o?: number; w?: boolean }) {
  return <span aria-hidden="true" className={`inline-block h-2.5 rounded-sm align-middle ${w ? 'w-1' : 'w-2.5'}`} style={{ background: c, opacity: o }} />;
}

function GroundTruth({ episode, t, truth, onToggle, label }: { episode: LabEpisode; t: number; truth: boolean; onToggle: (v: boolean) => void; label: (n: string) => string }) {
  const states = episode.steps[t]?.nodes ?? [];
  return (
    <div className="rounded-xl border border-line px-4 py-3 text-xs">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-semibold text-muted">Ground truth (simulation) — hidden attacker stage, never observed by the policy</p>
        <label className="flex cursor-pointer items-center gap-2 text-muted">
          <input type="checkbox" checked={truth} onChange={e => onToggle(e.target.checked)} className="accent-[var(--color-brand)]" />
          Show on the map (for learning)
        </label>
      </div>
      {truth ? (
        <ul className="mt-2 flex flex-wrap gap-1.5">
          {states.map(s => <li key={s.node} className="rounded-full border border-line px-2 py-0.5"><Mono>{label(s.node)}</Mono> · attacker {STAGE_WORDS[s.hidden_stage_ground_truth]}</li>)}
        </ul>
      ) : <p className="mt-1 text-faint">Hidden by default. The trained defender only sees alert rates, anomaly scores, monitoring levels and its own actions.</p>}
    </div>
  );
}
