'use client';

import { useEffect, useMemo, useState } from 'react';
import { DefenseMap, type MapNode, type MapState } from '@/components/defense-map';
import { sampleSize } from '@/lib/lab';
import { actionInWords, policyName, scenarioName, SCORE_METRICS, scoreboard } from '@/lib/lab-plain';
import type { DefenseLabBundle, LabNodeState } from '@/lib/lab-types';

const INTERNET = 'internet';

/** What the defender observed and did to a node at this step, in map words. Never ground truth. */
export function observedState(s: LabNodeState): MapState {
  if (s.isolated) return 'isolated';
  if (s.rate_limited) return 'limited';
  if (s.reassessment_pending || s.monitoring_level > 0) return 'checking';
  if (s.anomaly_score >= 0.5) return 'attention';
  return 'healthy';
}

/**
 * Command-center view of the Defense Lab: a recorded evaluation of the trained defender, played on
 * the continuous-defense map, next to the held-out scores. Every value comes from the
 * validated bundle; the map shows observed state and defender actions only.
 */
export function LabCommandCenter({ bundle }: { bundle: DefenseLabBundle }) {
  const episode = bundle.episodes.find(e => e.policy === 'ddqn' && !e.compromised) ?? bundle.episodes.find(e => e.policy === 'ddqn') ?? bundle.episodes[0];
  const scenario = bundle.scenarios.find(s => s.name === episode?.scenario);
  const [t, setT] = useState(0);
  const [paused, setPaused] = useState(false);
  const steps = episode?.steps.length ?? 0;

  useEffect(() => {
    if (paused || steps === 0 || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const id = setInterval(() => setT(v => (v + 1) % steps), 650);
    return () => clearInterval(id);
  }, [paused, steps]);

  const nodes = useMemo<MapNode[]>(() => scenario ? [
    { id: INTERNET, label: 'Internet', kind: 'edge', critical: false },
    ...scenario.nodes.map(n => ({ id: n.name, label: n.name, kind: 'node', critical: n.criticality >= 0.7 })),
  ] : [], [scenario]);
  const links = useMemo<[string, string][]>(() => scenario ? [
    ...scenario.nodes.filter(n => n.exposed).map(n => [INTERNET, n.name] as [string, string]),
    ...scenario.edges,
  ] : [], [scenario]);
  if (!episode || !scenario) return null;

  const step = episode.steps[Math.min(t, steps - 1)];
  const states: Record<string, MapState> = { [INTERNET]: 'healthy', ...Object.fromEntries((step?.nodes ?? []).map(s => [s.node, observedState(s)])) };
  const metric = (key: string) => {
    const def = SCORE_METRICS.find(m => m.key === key)!;
    const cells = scoreboard(bundle, def);
    return { def, ai: cells.find(c => c.policy === 'ddqn'), rules: cells.find(c => c.policy === 'threshold_rules') };
  };
  const tiles = ['compromise_rate', 'service_uptime', 'false_disruption_rate'].map(metric);
  const games = sampleSize(bundle, null);

  return (
    <section aria-labelledby="command-title" className="demo-ink rounded-3xl p-5 md:p-8" data-testid="lab-command">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="label-mono text-white/55">Continuous defense · recorded evaluation</p>
          <h2 id="command-title" className="mt-2 text-2xl font-semibold tracking-tight md:text-3xl">The trained defender, watching a network</h2>
        </div>
        <button type="button" onClick={() => setPaused(p => !p)} className="rounded-md bg-white/10 px-3 py-1.5 text-xs text-white transition-colors hover:bg-white/20">{paused ? '▶ Resume' : '❚❚ Pause'}</button>
      </div>
      <div className="mt-6 grid gap-5">
        <div className="min-w-0">
          <DefenseMap
            nodes={nodes}
            links={links}
            states={states}
            title={`${scenarioName(scenario.name)} · step ${step?.t ?? 0} of ${scenario.horizon}`}
            footnote="Replay of a recorded isolated-network evaluation. States show what the defender observed and did — never the hidden attacker."
          />
          <p className="mt-3 text-sm text-white/80" aria-live="off">
            <span className="label-mono mr-2 text-white/50">Defender move</span>{step ? actionInWords(step.action) : '—'}
          </p>
        </div>
        <div className="grid content-start gap-3 md:grid-cols-3">
          {tiles.map(({ def, ai, rules }) => (
            <div key={def.key} className="rounded-2xl bg-white/[0.04] p-4 shadow-[inset_0_0_0_1px_rgba(255,255,255,0.07)]">
              <p className="label-mono text-white/50">{def.title}</p>
              <p className="mt-2 flex items-baseline gap-2">
                <span className="font-display text-3xl font-semibold tabular-nums">{ai?.value == null ? '—' : `${ai.value.toFixed(1)}%`}</span>
                <span className="text-xs text-white/55">{policyName('ddqn')}</span>
              </p>
              <p className="mt-1 text-xs text-white/55">
                {rules?.value == null ? '' : `${rules.value.toFixed(1)}% for ${policyName('threshold_rules').toLowerCase()}`} · {def.higherIsBetter ? 'higher is better' : 'lower is better'}
              </p>
            </div>
          ))}
          <p className="text-xs text-white/50 md:col-span-3">Pooled over {games.toLocaleString()} held-out evaluation runs per defender that it never trained on. Full intervals below.</p>
        </div>
      </div>
    </section>
  );
}
