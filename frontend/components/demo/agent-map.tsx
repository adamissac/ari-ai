'use client';

import { useMemo, useState } from 'react';
import type { DemoComponent, DemoRepo } from '@/lib/demo/data';
import { affected, componentStates, coreComponent, PHASES, plainStep, STATE_LABEL, TEAM_COLOR, ticks, type ComponentState, type Tick } from '@/lib/demo/agent-map';
import { SPEEDS, type Playback } from '@/lib/demo/replay';
import type { AgentId, AgentRunView, Analysis } from '@/lib/demo/scenarios';

type Status = 'queued' | 'running' | 'done' | 'skipped';
const STATUS_WORD: Record<Status, string> = { queued: 'Queued', running: 'Working', done: 'Done', skipped: 'Not needed' };

const KIND_ICON: Record<string, string> = { edge: '⇄', service: '◆', site: '◇', identity: '⚿', worker: '⟳', data: '▤', logging: '≡', endpoints: '⌂' };

/**
 * Seven-agent replay as a live map (pattern from Omen AI's change workspace): agents on the
 * left, the parts of the app this commit touches in the middle with a beam to the part the
 * active agent is checking, and what was found there on the right. Replay can be paused,
 * sped up or scrubbed. Illustrative (ADR 0013).
 */
export function AgentMap({ repo, commitSha, analysis, statuses, played, started, playback, accepted, offset }: {
  repo: DemoRepo;
  commitSha: string;
  analysis: Analysis;
  statuses: Record<AgentId, Status>;
  /** Agent steps finished so far (0 … all). */
  played: number;
  /** Whether the agents' phase has begun (after reading the change and the review). */
  started: boolean;
  playback: Playback;
  accepted: boolean;
  /** Playhead ticks spent before the first agent step (understanding + review). */
  offset: number;
}) {
  const all = useMemo(() => ticks(analysis, repo), [analysis, repo]);
  const touched = useMemo(() => affected(all, repo), [all, repo]);
  const current: Tick | undefined = started && played < all.length ? all[played] : undefined;
  const states = componentStates(all, played, repo, analysis, accepted, current);
  const [focus, setFocus] = useState<{ kind: 'component'; id: string } | { kind: 'agent'; id: AgentId } | null>(null);
  const following = focus === null;
  const view = focus ?? (current ? { kind: 'component' as const, id: current.component } : { kind: 'component' as const, id: coreComponent(repo) });

  return (
    <section className="amap" data-testid="demo-agents" aria-label="Seven agents at work">
      <ReplayBar playback={playback} total={all.length} played={played} offset={offset} current={current} analysis={analysis} />
      <div className="amap-grid">
        <ol className="amap-rail" aria-label="Agents in orchestrator order">
          {analysis.agents.map((agent, i) => {
            const status = statuses[agent.agent];
            const live = current?.agent === agent.agent;
            return (
              <li key={agent.agent}>
                <button
                  type="button"
                  className="amap-agent"
                  data-status={status}
                  aria-pressed={view.kind === 'agent' && view.id === agent.agent}
                  onClick={() => setFocus(view.kind === 'agent' && view.id === agent.agent ? null : { kind: 'agent', id: agent.agent })}
                  data-testid={`demo-agent-${agent.agent}`}
                  style={{ ['--team' as string]: TEAM_COLOR[agent.team] }}
                >
                  <span className="amap-agent-dot" aria-hidden="true" />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-2">
                      <span className="font-mono text-[0.65rem] text-white/35">{String(i + 1).padStart(2, '0')}</span>
                      <span className="text-sm font-semibold">{agent.label}</span>
                      <span className="ml-auto text-[0.65rem] uppercase tracking-wider text-white/45">{STATUS_WORD[status]}</span>
                    </span>
                    <span className="block truncate text-xs text-white/50">{live && current ? plainStep(current.step) : agent.job}</span>
                  </span>
                </button>
              </li>
            );
          })}
        </ol>

        <SystemMap repo={repo} commitSha={commitSha} states={states} touched={touched} current={current} analysis={analysis} selected={view.kind === 'component' ? view.id : null} onSelect={id => setFocus({ kind: 'component', id })} />

        <aside className="amap-inspect" aria-live="polite">
          {view.kind === 'agent'
            ? <AgentDetail agent={analysis.agents.find(a => a.agent === view.id)!} status={statuses[view.id]} />
            : <ComponentDetail component={repo.components.find(c => c.id === view.id)!} state={states[view.id] ?? 'outside'} done={all.slice(0, played).filter(t => t.component === view.id)} live={current?.component === view.id ? current : undefined} />}
          {!following && <button type="button" className="mt-4 text-xs text-white/50 underline-offset-2 hover:text-white hover:underline" onClick={() => setFocus(null)}>Follow the active agent</button>}
        </aside>
      </div>
    </section>
  );
}

function ReplayBar({ playback, total, played, offset, current, analysis }: { playback: Playback; total: number; played: number; offset: number; current?: Tick; analysis: Analysis }) {
  const recording = playback.playing;
  const activePhase = current ? PHASES.findIndex(p => p.agents.includes(current.agent)) : -1;
  const label = current ? `${analysis.agents.find(a => a.agent === current.agent)?.label} · ${plainStep(current.step)}` : played >= total ? 'All seven agents finished' : 'Reading the change before the agents start';
  return (
    <div className="amap-bar">
      <div className="flex min-w-0 flex-wrap items-center gap-3">
        <span className="amap-rec" data-on={recording || undefined}>{recording ? 'Replaying' : played >= total ? 'Recorded' : 'Paused'}</span>
        <span className="min-w-0 truncate text-sm text-white/80" data-testid="demo-agent-now">{label}</span>
      </div>
      <ol className="amap-phases" aria-label="Phases">
        {PHASES.map((p, i) => (
          <li key={p.label} data-state={played >= total || i < activePhase ? 'done' : i === activePhase ? 'active' : 'todo'}>{p.label}</li>
        ))}
      </ol>
      <div className="amap-controls">
        <button type="button" className="amap-btn" onClick={playback.toggle} aria-label={playback.playing ? 'Pause replay' : 'Play replay'} data-testid="demo-play">
          {playback.playing ? '❚❚' : '▶'}
        </button>
        <input
          type="range" min={0} max={total + offset} value={Math.min(played + offset, total + offset)}
          onChange={e => playback.seek(Number(e.target.value))}
          aria-label="Replay position" className="amap-scrub"
        />
        <span className="font-mono text-[0.7rem] tabular-nums text-white/50">{played}/{total} steps</span>
        <span className="amap-speeds" role="group" aria-label="Replay speed">
          {SPEEDS.map(s => <button key={s} type="button" aria-pressed={playback.speed === s} onClick={() => playback.setSpeed(s)}>{s}×</button>)}
        </span>
      </div>
    </div>
  );
}

const half = (xs: DemoComponent[]) => Math.ceil(xs.length / 2);
const rowY = (row: number, rows: number) => ((row + 0.5) / rows) * 100;

function SystemMap({ repo, commitSha, states, touched, current, analysis, selected, onSelect }: {
  repo: DemoRepo; commitSha: string; states: Record<string, ComponentState>; touched: Set<string>; current?: Tick; analysis: Analysis; selected: string | null; onSelect: (id: string) => void;
}) {
  const h = half(repo.components);
  const left = repo.components.slice(0, h);
  const right = repo.components.slice(h);
  const idx = current ? repo.components.findIndex(c => c.id === current.component) : -1;
  const target = idx < 0 ? null : idx < h ? { side: 'left' as const, y: rowY(idx, left.length) } : { side: 'right' as const, y: rowY(idx - h, right.length) };
  const agent = current ? analysis.agents.find(a => a.agent === current.agent) : undefined;
  const color = current ? TEAM_COLOR[current.team] : '#fff';
  const files = analysis.review.diff.length;
  const card = (c: DemoComponent) => (
    <li key={c.id}>
      <button
        type="button"
        className="amap-node"
        data-state={states[c.id]}
        aria-pressed={selected === c.id}
        onClick={() => onSelect(c.id)}
        data-testid={`demo-node-${c.id}`}
        style={current?.component === c.id ? { ['--beam' as string]: color } : undefined}
      >
        <span className="flex items-center gap-2">
          <span aria-hidden="true" className="amap-icon">{KIND_ICON[c.kind] ?? '◆'}</span>
          <span className="truncate text-sm font-medium">{c.label}</span>
          {c.critical && <span className="amap-crit">critical</span>}
        </span>
        <span className="amap-node-state">{current?.component === c.id && agent ? `${agent.label} · ${plainStep(current.step).toLowerCase()}` : STATE_LABEL[states[c.id] ?? 'outside']}</span>
      </button>
    </li>
  );
  return (
    <div className="amap-map" role="group" aria-label="Parts of the app this commit touches">
      <ul className="amap-col">{left.map(card)}</ul>
      <div className="amap-hub-wrap">
        <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          {([['left', left], ['right', right]] as const).map(([side, items]) => {
            const edge = side === 'left' ? 0 : 100;
            const bus = side === 'left' ? 10 : 90;
            const hub = side === 'left' ? 20 : 80;
            const ys = items.map((_, i) => rowY(i, items.length));
            return (
              <g key={side} className="amap-wire">
                {ys.map((y, i) => <line key={items[i]!.id} x1={edge} y1={y} x2={bus} y2={y} vectorEffect="non-scaling-stroke" data-touched={touched.has(items[i]!.id) || undefined} />)}
                {ys.length > 0 && <line x1={bus} y1={Math.min(...ys)} x2={bus} y2={Math.max(...ys)} vectorEffect="non-scaling-stroke" />}
                <line x1={bus} y1={50} x2={hub} y2={50} vectorEffect="non-scaling-stroke" />
              </g>
            );
          })}
          {target && (
            <polyline
              key={`${current?.agent}-${current?.index}`}
              className="amap-beam"
              points={`${target.side === 'left' ? 0 : 100},${target.y} ${target.side === 'left' ? 10 : 90},${target.y} ${target.side === 'left' ? 10 : 90},50 ${target.side === 'left' ? 20 : 80},50`}
              stroke={color}
              vectorEffect="non-scaling-stroke"
            />
          )}
        </svg>
        <div className="amap-hub" style={current ? { ['--beam' as string]: color } : undefined}>
          <span className="label-mono text-white/45">This commit</span>
          <span className="mt-1 block font-mono text-sm text-white">{commitSha.slice(0, 7)}</span>
          <span className="mt-1 block text-[0.7rem] text-white/50">{files} file{files === 1 ? '' : 's'} · {touched.size} of {repo.components.length} parts touched</span>
        </div>
      </div>
      <ul className="amap-col">{right.map(card)}</ul>
    </div>
  );
}

const LATEST = 4;

function ComponentDetail({ component, state, done, live }: { component: DemoComponent; state: ComponentState; done: Tick[]; live?: Tick }) {
  return (
    <div data-testid="demo-node-detail">
      <p className="label-mono text-white/45">Part of the app</p>
      <p className="mt-1 text-lg font-semibold">{component.label}</p>
      <p className="amap-pill mt-2" data-state={state}>{STATE_LABEL[state]}</p>
      {done.length === 0 && !live && <p className="mt-4 text-sm text-white/55">{state === 'outside' ? 'This commit does not touch it, so the agents leave it alone.' : 'No agent has reached this part yet.'}</p>}
      {(done.length > 0 || live) && (
        <>
          <ol className="mt-4 flex flex-col gap-3">
            {live && <TickLine tick={live} live />}
            {[...done].reverse().slice(0, LATEST).map((t, i) => <TickLine key={i} tick={t} />)}
          </ol>
          {done.length > LATEST && (
            <details className="amap-more mt-3">
              <summary>Earlier checks here ({done.length - LATEST})</summary>
              <ol className="mt-3 flex flex-col gap-3">{[...done].reverse().slice(LATEST).map((t, i) => <TickLine key={i} tick={t} />)}</ol>
            </details>
          )}
        </>
      )}
    </div>
  );
}

function TickLine({ tick, live = false }: { tick: Tick; live?: boolean }) {
  return (
    <li className="amap-tick" data-live={live || undefined} style={{ ['--team' as string]: TEAM_COLOR[tick.team] }}>
      <p className="text-sm text-white/90"><span className="font-semibold capitalize">{tick.agent}</span> · {plainStep(tick.step)}</p>
      <p className={`text-xs ${tick.step.outcome === 'denied' ? 'text-[#ffc36b]' : 'text-white/55'}`}>{live ? 'working…' : tick.step.outcome === 'denied' ? `Blocked by policy: ${tick.step.result}` : tick.step.result}</p>
    </li>
  );
}

function AgentDetail({ agent, status }: { agent: AgentRunView; status: Status }) {
  return (
    <div>
      <p className="label-mono text-white/45">{agent.team === 'Independent' ? 'Independent check' : `${agent.team} team`}</p>
      <p className="mt-1 text-lg font-semibold">{agent.label} <span className="text-sm font-normal text-white/50">· {agent.job}</span></p>
      <p className="mt-3 text-sm text-white/85" data-testid="demo-agent-outcome">
        {status === 'queued' ? 'Waiting for the previous agent to hand off.' : status === 'running' ? 'Working…' : agent.outcome}
      </p>
      {(status === 'done' || status === 'skipped') && <p className="mt-3 text-xs text-white/55" data-testid="demo-agent-handoff">Hands off: {agent.handoff}</p>}
      {agent.steps.length > 0 && (
        <details className="amap-more mt-4">
          <summary>See every step ({agent.steps.length})</summary>
          <ol className="mt-3 flex flex-col gap-2.5" data-testid="demo-agent-steps">
            {agent.steps.map((step, i) => (
              <li key={i} className="text-xs">
                <p className="text-white/85">{plainStep(step)} <span className="font-mono text-white/40">{step.tool}</span></p>
                <p className="text-white/50">{step.input}</p>
                <p className={step.outcome === 'denied' ? 'text-[#ffc36b]' : 'text-white/60'}>{step.outcome === 'denied' ? 'Blocked by policy: ' : '→ '}{step.result}</p>
              </li>
            ))}
          </ol>
        </details>
      )}
      {agent.evidence.length > 0 && status === 'done' && (
        <details className="amap-more mt-2">
          <summary>Evidence ({agent.evidence.length})</summary>
          <ul className="mt-2 flex flex-col gap-1.5 text-xs text-white/70">{agent.evidence.map(e => <li key={e}>▸ {e}</li>)}</ul>
        </details>
      )}
    </div>
  );
}
