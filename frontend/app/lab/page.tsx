'use client';

import { useEffect, useState } from 'react';
import type { Project } from '@hackatl/frontend-transport';
import { DefenseSwitch } from '@/components/defense-switch';
import { ConsoleSide } from '@/components/lab-console';
import { observedState } from '@/components/lab-command';
import { ReplayStage } from '@/components/lab-replay';
import { OptionalSession, useOptionalSession } from '@/components/session';
import { Empty, ErrorState, inputClass, Loading, Mono, Panel } from '@/components/ui';
import { defenderCountPhrase } from '@/components/lab-copy';
import { api } from '@/lib/api';
import { DEMO_ONLY } from '@/lib/deployment';
import { sampleSize } from '@/lib/lab';
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
  const [scenarioId, setScenarioId] = useState('');
  const [currentStep, setCurrentStep] = useState(0);
  const bundle: Load<BundleResponse> = loaded && loaded.protocol === protocol ? loaded.result : { status: 'loading' };
  const readyBundle = bundle.status === 'ready' ? bundle.data.bundle : null;
  const defenderEpisodes = readyBundle?.episodes.filter(e => e.policy === 'ddqn') ?? [];
  const scenarios = [...new Set(defenderEpisodes.map(e => e.scenario))];
  const selectedScenario = scenarios.includes(scenarioId) ? scenarioId : scenarios[0] ?? '';
  const episode = defenderEpisodes.find(e => e.scenario === selectedScenario)
  const scenario = readyBundle?.scenarios.find(s => s.name === episode?.scenario);
  const step = episode?.steps.find(s => s.t === currentStep) ?? episode?.steps[0];
  const openAlerts = step?.nodes.filter(node => observedState(node) === 'attention').length ?? 0;

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
      <header className="mb-8 border-b border-line pb-6">
        <p className="label-mono text-faint">Defense Lab</p>
        <h1 className="mt-2 text-2xl font-semibold md:text-3xl">Network defense</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted" data-testid="lab-intro">
          What your team sees while Ari&apos;s defender watches the network.
        </p>
        {readyBundle && scenario && (
          <div className="mt-5 border-y border-line">
            <dl className="grid grid-cols-2 gap-4 py-3 sm:grid-cols-4">
              <div>
                <dt className="label-mono text-faint">Network</dt>
                <dd className="mt-1 text-sm font-medium text-ink">{scenarioName(scenario.name)}</dd>
              </div>
              <div>
                <dt className="label-mono text-faint">Services watched</dt>
                <dd className="mt-1 text-sm font-medium text-ink">{scenario.nodes.length}</dd>
              </div>
              <div>
                <dt className="label-mono text-faint">Defender</dt>
                <dd className="mt-1 flex items-center gap-2 text-sm font-medium text-ink">
                  <span aria-hidden="true" className="h-2 w-2 rounded-full bg-ok" />
                  Active · recommendation-only
                </dd>
              </div>
              <div>
                <dt className="label-mono text-faint">Open alerts</dt>
                <dd className="mt-1 text-sm font-medium text-ink">{openAlerts}</dd>
              </div>
            </dl>
            <div className="grid gap-4 border-t border-line py-3 sm:grid-cols-2">
              <label className="flex min-w-0 flex-col gap-1">
                <span className="label-mono text-faint">Attacker scenario</span>
                <select
                  aria-label="Attacker scenario"
                  className={inputClass}
                  value={selectedScenario}
                  onChange={e => { setScenarioId(e.target.value); setCurrentStep(0); }}
                >
                  {scenarios.map(s => <option key={s} value={s}>{scenarioName(s)}</option>)}
                </select>
              </label>
              {protocols.status === 'ready' && protocols.data.length > 0 && (
                <label className="flex min-w-0 flex-col gap-1">
                  <span className="label-mono text-faint">Evaluation run</span>
                  <select
                    aria-label="Evaluation run"
                    className={inputClass}
                    value={protocol}
                    onChange={e => { setProtocol(e.target.value); setCurrentStep(0); }}
                  >
                    {protocols.data.map(p => <option key={p} value={p}>{p}</option>)}
                  </select>
                </label>
              )}
            </div>
          </div>
        )}
        <p role="note" className="label-mono mt-3 inline-flex rounded-full border border-line px-3 py-1 text-faint" data-testid="lab-caveat">
          Recorded run · test network
        </p>
      </header>
      {protocols.status === 'loading' && <Loading label="Finding evaluation runs" />}
      {protocols.status === 'error' && <ErrorState error={protocols.error} context="Could not list evaluation runs" />}
      {protocols.status === 'ready' && protocols.data.length === 0 && <Empty>No committed evaluation bundle (rl-defense/results/protocol-*/defense_lab.json) was found.</Empty>}
      {protocol && bundle.status === 'loading' && <Loading label={`Loading ${protocol}`} />}
      {bundle.status === 'error' && <ErrorState error={bundle.error} context="Evaluation bundle rejected" />}
      {bundle.status === 'ready' && <Lab data={bundle.data} scenarioId={selectedScenario} onStep={setCurrentStep} />}
    </>
  );
}

function SignedInDefenseProjects() {
  const session = useOptionalSession();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const userId = session?.me.user.id ?? null;

  useEffect(() => {
    if (!userId) return;
    const controller = new AbortController();
    api().projects({ signal: controller.signal }).then(
      page => { if (!controller.signal.aborted) setProjects(page.items); },
      () => { if (!controller.signal.aborted) setProjects(null); },
    );
    return () => controller.abort();
  }, [userId]);

  if (!userId || projects === null) return null;

  return (
    <Panel title="Your 24/7 defense" className="mb-6">
      {projects.length === 0 ? (
        <p className="text-sm text-muted">No projects yet.</p>
      ) : (
        <ul className="divide-y divide-line">
          {projects.map(project => (
            <li key={project.id} className="flex flex-wrap items-start justify-between gap-4 py-3 first:pt-0 last:pb-0">
              <p className="pt-2 text-sm font-medium">{project.name}</p>
              <DefenseSwitch
                project={project}
                onChange={next => setProjects(current => current?.map(item => item.id === next.id ? next : item) ?? null)}
              />
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function Lab({ data, scenarioId, onStep }: { data: BundleResponse; scenarioId: string; onStep: (t: number) => void }) {
  const { bundle, provenance } = data;
  const defenderEpisodes = bundle.episodes.filter(e => e.policy === 'ddqn');
  const episode = defenderEpisodes.find(e => e.scenario === scenarioId)
  const scenario = bundle.scenarios.find(s => s.name === episode?.scenario);
  return (
    <div className="flex flex-col gap-16">
      <LiveView episode={episode} scenario={scenario} onStep={onStep} />
      <Scoreboard bundle={bundle} />
      {!DEMO_ONLY && <OptionalSession><SignedInDefenseProjects /></OptionalSession>}
      <details className="group rounded-2xl border border-line bg-panel" data-testid="lab-details">
        <summary className="flex cursor-pointer list-none items-center gap-2 px-5 py-4 text-sm font-semibold">
          <span aria-hidden="true" className="inline-block transition-transform group-open:rotate-90">▸</span>
          Where these numbers come from
        </summary>
        <div className="border-t border-line p-5">
          <Panel title="Provenance">
            <dl className="grid gap-x-4 gap-y-1 text-xs text-muted sm:grid-cols-[auto_1fr]">
              <dt>Source</dt><dd><Mono>{provenance.path}</Mono> — committed evaluation artifact, validated against <Mono>{provenance.schemaPath}</Mono>. Not yet served by the backend API.</dd>
              <dt>Environment</dt><dd><Mono>{bundle.env_id}</Mono> · schema {bundle.schema_version}</dd>
              <dt>Run</dt><dd><Mono>{bundle.source_run}</Mono> at commit <Mono>{bundle.git_sha.slice(0, 12)}</Mono></dd>
              <dt>Training seeds</dt><dd>{bundle.training_seeds.join(', ')} · {bundle.episodes_per_config_per_seed} episodes per held-out config per seed</dd>
            </dl>
          </Panel>
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
const HEADLINE_KEYS = new Set(HEADLINE.map(h => h.key));

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
    <dl className="lab-headline mt-6" data-testid="lab-takeaway" aria-label="Performance summary" aria-description={keyTakeaway(bundle) ?? undefined}>
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
  const metrics = SCORE_METRICS.filter(m => HEADLINE_KEYS.has(m.key))
    .map(metric => ({ metric, cells: scoreboard(bundle, metric) }))
    .filter(m => !m.cells.every(c => c.value === null));
  return (
    <section aria-labelledby="score-title" data-testid="lab-scoreboard" className="py-14 md:py-20">
      <p className="lab-eyebrow">Performance</p>
      <h2 id="score-title" className="mt-2 text-2xl font-semibold tracking-tight md:text-3xl">How it performs</h2>
      <p className="mt-2 max-w-3xl text-sm text-muted">
        {defenderCountPhrase(bundle.metrics.length, true)}, tested on {n.toLocaleString()} held-out runs across {bundle.scenarios.length} attacker scenarios and {bundle.training_seeds.length} training seeds.
      </p>
      <Headline bundle={bundle} />
      <div className="mt-8 grid grid-cols-1 gap-4 lg:grid-cols-3">
        {metrics.map(({ metric, cells }) => {
          const top = Math.max(...cells.map(x => x.hi ?? x.value ?? 0), 1);
          const pct = (x: number | null) => (x === null ? 0 : Math.min(100, Math.max(0, metric.percent ? x : (x / top) * 100)));
          return (
            <figure key={metric.key} className="lab-score-card" data-testid={`score-${metric.key}`}>
              <figcaption className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                <span className="font-semibold tracking-tight text-ink">{metric.title}</span>
                <Direction higher={metric.higherIsBetter} />
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
                        <span className="sr-only"> 95% range {fmtRange(metric, c.lo, c.hi)}</span>
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
    </section>
  );
}

function LiveView({ episode, scenario, onStep }: { episode: LabEpisode | undefined; scenario: DefenseLabBundle['scenarios'][number] | undefined; onStep: (t: number) => void }) {
  return (
    <section aria-labelledby="replay-title">
      <p className="lab-eyebrow">Defender activity</p>
      <h2 id="replay-title" className="mt-2 text-2xl font-semibold tracking-tight md:text-3xl">Network view</h2>
      {!episode || !scenario ? <div className="mt-4"><Empty>This bundle has no recorded episodes.</Empty></div> : (
        <div className="lab-replay-card mt-6 p-5">
          <ReplayStage
            key={`${episode.scenario}-${episode.episode_seed}`}
            episode={episode}
            scenario={scenario}
            autoPlay
            onStep={onStep}
            side={({ episode: currentEpisode, scenario: currentScenario, t }) => (
              <ConsoleSide key={`${currentScenario.name}-${currentEpisode.episode_seed}`} episode={currentEpisode} scenario={currentScenario} t={t} />
            )}
          />
        </div>
      )}
    </section>
  );
}
