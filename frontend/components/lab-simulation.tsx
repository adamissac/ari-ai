'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import type { LabPolicyKind, LabSimulationEpisode, LabSimulationResult, LabSimulationStatus, LabSimulationStep } from '@hackatl/frontend-transport';
import { useOptionalSession } from '@/components/session';
import { Button, ErrorState, inputClass, Loading, Mono, Tag } from '@/components/ui';
import { api } from '@/lib/api';

/**
 * Runs a simulated episode on the backend and steps through what the policy saw and did.
 * Every number on screen comes from the backend response for the request shown; there is
 * no local fallback. If the engine is unavailable the panel says so and offers nothing.
 */

type Load<T> = { status: 'idle' } | { status: 'loading' } | { status: 'ready'; data: T } | { status: 'error'; error: unknown };

const POLICY_LABEL: Record<LabPolicyKind, string> = {
  ddqn_trained: 'Trained policy (Double DQN checkpoint)',
  ddqn_untrained: 'Untrained network (same model, no training)',
  random: 'Random valid action',
  noop: 'No action',
  threshold_rules: 'Threshold rules',
};
const SOURCE_LABEL = { learned_checkpoint: 'Learned checkpoint', untrained_network: 'Untrained network', scripted_baseline: 'Scripted baseline' } as const;
const SOURCE_TONE = { learned_checkpoint: 'ok', untrained_network: 'warn', scripted_baseline: 'neutral' } as const;
const STEP_MS = 350;
const MAX_SEED = 2147483647;

const fmt = (x: number, digits = 2) => x.toFixed(digits);
const signed = (x: number) => `${x > 0 ? '+' : ''}${x.toFixed(3)}`;

export function LabSimulation() {
  const session = useOptionalSession();
  return (
    <section aria-labelledby="sim-title" data-testid="lab-simulation">
      <p className="lab-eyebrow">Simulation</p>
      <h2 id="sim-title" className="mt-2 text-2xl font-semibold tracking-tight md:text-3xl">Run an episode</h2>
      <p className="mt-2 max-w-3xl text-sm text-muted">
        Starts a new simulated episode on the server and shows each decision: what the policy observed, which actions were allowed, how it scored them, what it chose and the reward it received.
      </p>
      <div className="mt-6">
        {session
          ? <Runner key={session.me.user.id} />
          : <p className="rounded-lg border border-dashed border-control/60 bg-panel-2/40 px-4 py-6 text-sm text-muted" data-testid="sim-signed-out">Sign in to run a simulation. The recorded run above needs no account.</p>}
      </div>
    </section>
  );
}

function Runner() {
  const [status, setStatus] = useState<Load<LabSimulationStatus>>({ status: 'loading' });
  const [attempt, setAttempt] = useState(0);
  const [scenario, setScenario] = useState('');
  const [policy, setPolicy] = useState<LabPolicyKind>('ddqn_trained');
  const [seed, setSeed] = useState('1000');
  const [run, setRun] = useState<Load<LabSimulationResult>>({ status: 'idle' });
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const inFlight = useRef<AbortController | null>(null);

  useEffect(() => {
    const c = new AbortController();
    api().labSimulationStatus({ signal: c.signal }).then(
      data => { setStatus({ status: 'ready', data }); setScenario(s => s || data.scenarios[0]?.name || ''); },
      (error: unknown) => { if (!c.signal.aborted) setStatus({ status: 'error', error }); },
    );
    return () => c.abort();
  }, [attempt]);
  useEffect(() => () => inFlight.current?.abort(), []);

  const episode = run.status === 'ready' ? run.data.episode : null;
  const last = episode ? episode.steps.length - 1 : 0;
  useEffect(() => {
    if (!playing || !episode) return;
    const id = window.setInterval(() => setT(current => {
      if (current >= last) { setPlaying(false); return current; }
      return current + 1;
    }), STEP_MS);
    return () => window.clearInterval(id);
  }, [playing, episode, last]);

  const seedValue = /^\d{1,10}$/.test(seed) && Number(seed) <= MAX_SEED ? Number(seed) : null;
  const start = (episodeSeed: number) => {
    inFlight.current?.abort();
    const c = new AbortController();
    inFlight.current = c;
    setPlaying(false);
    setT(0);
    setRun({ status: 'loading' });
    api().runLabSimulation({ scenario, policy, episode_seed: episodeSeed }, { signal: c.signal }).then(
      data => { if (!c.signal.aborted) { setRun({ status: 'ready', data }); setPlaying(true); } },
      (error: unknown) => { if (!c.signal.aborted) setRun({ status: 'error', error }); },
    );
  };
  const stop = () => { inFlight.current?.abort(); setPlaying(false); setT(0); setRun({ status: 'idle' }); };

  if (status.status === 'loading' || status.status === 'idle') return <Loading label="Checking the simulation engine" />;
  if (status.status === 'error') return <ErrorState error={status.error} context="Could not reach the simulation engine" onRetry={() => { setStatus({ status: 'loading' }); setAttempt(n => n + 1); }} />;
  const info = status.data;
  if (!info.available) {
    return (
      <div role="alert" className="rounded-md border border-warn/40 bg-warn/5 p-3 text-sm" data-testid="sim-unavailable">
        <p className="font-semibold text-ink">Simulation unavailable</p>
        <p className="mt-1 text-muted">{info.unavailable_reason}</p>
        <p className="mt-1 text-muted">Nothing can be run here, and no substitute data is shown.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="grid gap-4 rounded-xl border border-line bg-panel p-5 sm:grid-cols-[1fr_1fr_8rem_auto] sm:items-end">
        <label className="flex min-w-0 flex-col gap-1">
          <span className="label-mono text-faint">Scenario</span>
          <select aria-label="Simulation scenario" className={inputClass} value={scenario} onChange={e => setScenario(e.target.value)}>
            {info.scenarios.map(s => <option key={s.name} value={s.name}>{s.name} ({s.split === 'eval' ? 'held-out' : 'training'})</option>)}
          </select>
        </label>
        <label className="flex min-w-0 flex-col gap-1">
          <span className="label-mono text-faint">Policy</span>
          <select aria-label="Simulation policy" className={inputClass} value={policy} onChange={e => setPolicy(e.target.value as LabPolicyKind)}>
            {info.policies.map(p => <option key={p} value={p}>{POLICY_LABEL[p]}</option>)}
          </select>
        </label>
        <label className="flex min-w-0 flex-col gap-1">
          <span className="label-mono text-faint">Episode seed</span>
          <input aria-label="Episode seed" inputMode="numeric" className={inputClass} value={seed} onChange={e => setSeed(e.target.value)} aria-invalid={seedValue === null} />
        </label>
        <Button variant="primary" className="h-9" disabled={seedValue === null || !scenario || run.status === 'loading'} onClick={() => seedValue !== null && start(seedValue)} data-testid="sim-run">
          {episode ? 'Run again' : 'Run simulation'}
        </Button>
        <p className="text-xs text-muted sm:col-span-4" data-testid="sim-label">
          {info.label} Trained policy: <Mono>{info.checkpoint?.policy_version}</Mono>.
          {seedValue === null && <span className="text-bad"> Seed must be a whole number from 0 to {MAX_SEED}.</span>}
        </p>
      </div>
      {run.status === 'loading' && <Loading label="Running the episode on the server" />}
      {run.status === 'error' && <ErrorState error={run.error} context="The simulation did not run" onRetry={seedValue === null ? undefined : () => start(seedValue)} />}
      {episode && (
        <Episode
          episode={episode} t={Math.min(t, last)} playing={playing}
          onPlay={() => { if (t >= last) setT(0); setPlaying(true); }}
          onPause={() => setPlaying(false)}
          onStep={() => { setPlaying(false); setT(current => Math.min(last, current + 1)); }}
          onReset={() => { setPlaying(false); setT(0); }}
          onStop={stop}
          onSeek={value => { setPlaying(false); setT(value); }}
        />
      )}
    </div>
  );
}

function Episode({ episode, t, playing, onPlay, onPause, onStep, onReset, onStop, onSeek }: {
  episode: LabSimulationEpisode; t: number; playing: boolean;
  onPlay: () => void; onPause: () => void; onStep: () => void; onReset: () => void; onStop: () => void; onSeek: (t: number) => void;
}) {
  const steps = episode.steps;
  const step = steps[t]!;
  const last = steps.length - 1;
  const cumulative = useMemo(
    () => steps.reduce<number[]>((acc, s) => [...acc, (acc[acc.length - 1] ?? 0) + s.reward], []),
    [steps],
  );
  const p = episode.policy;
  const finished = t === last;
  return (
    <div className="rounded-xl border border-line bg-panel" data-testid="sim-episode">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3">
        <div className="min-w-0 text-sm">
          <p className="flex flex-wrap items-center gap-x-3 gap-y-1" data-testid="sim-policy">
            <Tag tone={SOURCE_TONE[p.source]}>{SOURCE_LABEL[p.source]}</Tag>
            <span className="font-medium text-ink">{POLICY_LABEL[p.kind]}</span>
          </p>
          <p className="mt-1 text-xs text-muted" data-testid="sim-provenance">
            {p.source === 'learned_checkpoint' && <>Checkpoint <Mono>{p.checkpoint_sha256!.slice(0, 12)}</Mono> · {p.gradient_updates.toLocaleString()} gradient updates · </>}
            {p.source === 'untrained_network' && <>0 gradient updates · </>}
            {episode.scenario.name} · seed {episode.episode_seed} · {episode.env_id}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Playback">
          {playing
            ? <Button onClick={onPause} data-testid="sim-pause">Pause</Button>
            : <Button onClick={onPlay} data-testid="sim-play">{finished ? 'Replay' : t === 0 ? 'Play' : 'Resume'}</Button>}
          <Button onClick={onStep} disabled={finished} data-testid="sim-step">Step</Button>
          <Button onClick={onReset} disabled={t === 0} data-testid="sim-reset">Reset</Button>
          <Button variant="ghost" onClick={onStop} data-testid="sim-stop">Stop</Button>
        </div>
      </header>
      <div className="px-5 py-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
          <p data-testid="sim-progress"><span className="font-medium text-ink">Step {t + 1} of {steps.length}</span><span className="text-muted"> · horizon {episode.scenario.horizon}</span></p>
          <p className="text-muted">Return so far <span className="font-mono text-ink" data-testid="sim-return">{fmt(cumulative[t]!)}</span></p>
        </div>
        <ReturnChart cumulative={cumulative} t={t} />
        <input
          type="range" aria-label="Episode step" className="mt-2 w-full" min={0} max={last} value={t}
          onChange={e => onSeek(Number(e.target.value))}
        />
      </div>
      <div className="grid gap-px border-t border-line bg-line lg:grid-cols-2">
        <Decision step={step} episode={episode} />
        <Outcome step={step} episode={episode} />
        <div className="bg-panel p-5 lg:col-span-2"><Observation step={step} episode={episode} /></div>
      </div>
      {finished && (
        <p className="border-t border-line px-5 py-3 text-sm" data-testid="sim-summary">
          <span className="font-medium text-ink">Episode ended {episode.summary.terminated ? 'early: the database was lost' : 'at the time limit'}.</span>{' '}
          <span className="text-muted">
            Total return {fmt(episode.summary.total_return)}.{' '}
            {episode.summary.ever_impact ? `Attacker reached impact on ${episode.summary.impact_nodes.join(', ')}.` : 'The attacker never reached impact.'}
          </span>
        </p>
      )}
    </div>
  );
}

function ReturnChart({ cumulative, t }: { cumulative: number[]; t: number }) {
  const lo = Math.min(0, ...cumulative);
  const hi = Math.max(0, ...cumulative);
  const span = hi - lo || 1;
  const n = Math.max(1, cumulative.length - 1);
  const x = (i: number) => (i / n) * 100;
  const y = (v: number) => 30 - ((v - lo) / span) * 28 - 1;
  const points = cumulative.map((v, i) => `${x(i).toFixed(2)},${y(v).toFixed(2)}`).join(' ');
  return (
    <svg viewBox="0 0 100 30" preserveAspectRatio="none" className="mt-3 h-16 w-full" role="img" aria-label={`Cumulative return, ${fmt(cumulative[t]!)} at this step, ${fmt(cumulative[cumulative.length - 1]!)} at the end`}>
      <line x1="0" x2="100" y1={y(0)} y2={y(0)} stroke="var(--color-line)" strokeWidth="0.4" vectorEffect="non-scaling-stroke" />
      <polyline points={points} fill="none" stroke="var(--color-faint)" strokeWidth="1.2" vectorEffect="non-scaling-stroke" />
      <line x1={x(t)} x2={x(t)} y1="0" y2="30" stroke="var(--color-brand)" strokeWidth="1.2" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function Decision({ step, episode }: { step: LabSimulationStep; episode: LabSimulationEpisode }) {
  const valid = step.action_mask.filter(Boolean).length;
  const q = step.q_values;
  const ranked = q
    ? step.action_mask.map((ok, a) => ({ a, ok, q: q[a]! })).filter(r => r.ok).sort((l, r) => r.q - l.q).slice(0, 5)
    : [];
  const qs = ranked.map(r => r.q);
  const lo = Math.min(...qs), hi = Math.max(...qs);
  return (
    <div className="bg-panel p-5" data-testid="sim-decision">
      <h3 className="label-mono text-faint">Decision</h3>
      <p className="mt-2 text-lg font-semibold text-ink" data-testid="sim-action">{step.action_label}</p>
      <p className="mt-1 text-xs text-muted" data-testid="sim-mask">{valid} of {episode.action_labels.length} actions were allowed at this step.</p>
      {q ? (
        <>
          <p className="mt-4 text-xs text-muted">Highest-scored allowed actions (Q-values are scores, not probabilities)</p>
          <ol className="mt-2 flex flex-col gap-1.5" data-testid="sim-q">
            {ranked.map(r => (
              <li key={r.a} className="grid grid-cols-[minmax(0,11rem)_1fr_4rem] items-center gap-2 text-xs">
                <span className={`truncate ${r.a === step.action ? 'font-semibold text-ink' : 'text-muted'}`}>{episode.action_labels[r.a]}</span>
                <span className="relative block h-2 rounded-full bg-panel-2" aria-hidden="true">
                  <span className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${hi === lo ? 100 : 8 + ((r.q - lo) / (hi - lo)) * 92}%`, background: r.a === step.action ? 'var(--color-brand)' : 'var(--color-faint)' }} />
                </span>
                <span className="text-right font-mono tabular-nums text-ink">{fmt(r.q, 3)}</span>
              </li>
            ))}
          </ol>
        </>
      ) : (
        <p className="mt-4 text-xs text-muted" data-testid="sim-no-q">This is a scripted baseline. It has no model, so there are no Q-values to show.</p>
      )}
    </div>
  );
}

function Outcome({ step, episode }: { step: LabSimulationStep; episode: LabSimulationEpisode }) {
  const parts = episode.reward_component_names.filter(c => step.reward_components[c] !== 0);
  return (
    <div className="bg-panel p-5" data-testid="sim-outcome">
      <h3 className="label-mono text-faint">Reward for this step</h3>
      <p className="mt-2 font-mono text-lg font-semibold text-ink" data-testid="sim-reward">{signed(step.reward)}</p>
      {parts.length === 0
        ? <p className="mt-1 text-xs text-muted">Every reward component was zero.</p>
        : (
          <dl className="mt-2 grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 text-xs" data-testid="sim-reward-parts">
            {parts.map(c => <div key={c} className="contents"><dt className="text-muted">{c.replaceAll('_', ' ')}</dt><dd className="text-right font-mono tabular-nums text-ink">{signed(step.reward_components[c]!)}</dd></div>)}
          </dl>
        )}
      <h3 className="label-mono mt-5 text-faint">State after the action</h3>
      <p className="mt-1 text-xs text-muted">Simulator ground truth. The policy never sees this.</p>
      <ul className="mt-2 flex flex-wrap gap-2 text-xs" data-testid="sim-truth">
        {episode.scenario.nodes.map((n, i) => {
          const stage = step.ground_truth_stages[i]!;
          return <li key={n.name} className="rounded-md border border-line px-2 py-1"><span className="text-muted">{n.name}</span> <span className={stage === 'none' ? 'text-ink' : 'font-semibold text-bad'}>{stage}</span></li>;
        })}
      </ul>
    </div>
  );
}

function Observation({ step, episode }: { step: LabSimulationStep; episode: LabSimulationEpisode }) {
  const nodes = episode.scenario.nodes.map(n => n.name);
  const cells = new Map(episode.feature_names.map((name, i) => [name, step.observation[i]!] as const));
  const perNode = [...new Set(episode.feature_names.filter(f => f.includes('.')).map(f => f.slice(f.indexOf('.') + 1)))];
  const globals = episode.feature_names.filter(f => !f.includes('.'));
  return (
    <div data-testid="sim-observation">
      <h3 className="label-mono text-faint">Observation</h3>
      <p className="mt-1 text-xs text-muted">The {episode.feature_names.length} values the policy saw before choosing. All are scaled to 0–1.</p>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[32rem] border-collapse text-xs">
          <thead>
            <tr className="text-left text-muted">
              <th scope="col" className="py-1 pr-3 font-normal">Signal</th>
              {nodes.map(n => <th key={n} scope="col" className="px-2 py-1 text-right font-medium text-ink">{n}</th>)}
            </tr>
          </thead>
          <tbody>
            {perNode.map(f => (
              <tr key={f} className="border-t border-line">
                <th scope="row" className="py-1 pr-3 text-left font-normal text-muted">{f.replaceAll('_', ' ')}</th>
                {nodes.map(n => {
                  const v = cells.get(`${n}.${f}`);
                  return <td key={n} className={`px-2 py-1 text-right font-mono tabular-nums ${v ? 'text-ink' : 'text-faint'}`}>{v === undefined ? '—' : fmt(v)}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-xs">
        {globals.map(f => <div key={f} className="flex gap-2"><dt className="text-muted">{f.replaceAll('_', ' ')}</dt><dd className="font-mono tabular-nums text-ink">{fmt(cells.get(f)!)}</dd></div>)}
      </dl>
    </div>
  );
}
