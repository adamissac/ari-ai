'use client';

import type { DefenseRecommendation, RLEvaluation, RLExplanation } from '@hackatl/frontend-transport';
import Link from 'next/link';
import { useState } from 'react';
import { QRanking, SimulationCaveat, SourceTag } from '@/components/live-defense/common';
import { Async, Button, Empty, ErrorState, Loading, Mono, Panel, Tag, Time } from '@/components/ui';
import { api } from '@/lib/api';
import { actionInWords, rankQValues, SIMULATION_CAVEAT, type LiveDefenseMode } from '@/lib/live-defense';
import { PREVIEW_RECOMMENDATIONS } from '@/lib/live-defense-preview';
import { num } from '@/lib/format';
import type { Resource } from '@/lib/use-resource';

export function Explainability({
  mode,
  recs,
  evals,
}: {
  mode: LiveDefenseMode;
  recs?: Resource<{ items: DefenseRecommendation[]; label: string }>;
  evals?: Resource<{ items: RLEvaluation[] }>;
}) {
  if (mode === 'layout-preview') return <PreviewExplain />;
  return (
    <div className="flex flex-col gap-4">
      <Panel title="Why a stored recommendation looks the way it does" actions={<SourceTag mode="live" />}>
        <SimulationCaveat />
        <p className="mt-3 text-sm text-muted">
          Q-values and occlusion contributions come from the recommendation the backend already stored.
          They explain a simulation-trained policy, not a live attack and not a confidence that something is happening now.
          Held-out scores live in the <Link className="text-accent hover:underline" href="/lab">Defense Lab</Link>.
        </p>
      </Panel>
      <Panel title="Stored recommendations">
        {recs ? (
          <Async resource={recs} label="recommendations">
            {page => (
              <>
                <p className="mb-3 text-xs text-faint">Backend label: {page.label}</p>
                {page.items.length === 0 ? <Empty>No recommendation has been requested for this project.</Empty> : (
                  <ul className="flex flex-col gap-3">{page.items.map(rec => <LiveRecommendation key={rec.id} rec={rec} />)}</ul>
                )}
              </>
            )}
          </Async>
        ) : <Empty>Recommendations were not requested.</Empty>}
      </Panel>
      <Panel title="Imported RL evaluations">
        {evals ? (
          <Async resource={evals} label="RL evaluations">
            {page => page.items.length === 0 ? (
              <Empty>No evaluation imported into this project. The Defense Lab reads the committed bundle directly.</Empty>
            ) : (
              <ul className="divide-y divide-line text-xs">
                {page.items.map(item => (
                  <li key={item.id} className="py-2">
                    <Mono>{item.id}</Mono> · protocol {item.protocol_version} · {item.checkpoint_ids.length} checkpoints · summary sha256 <Mono>{item.summary_sha256.slice(0, 12)}</Mono> · <Time iso={item.created_at} />
                    {item.simulation_derived && <Tag tone="warn" >simulation-derived</Tag>}
                  </li>
                ))}
              </ul>
            )}
          </Async>
        ) : <Empty>Evaluations were not requested.</Empty>}
      </Panel>
    </div>
  );
}

function LiveRecommendation({ rec }: { rec: DefenseRecommendation }) {
  const [exp, setExp] = useState<{ status: 'idle' } | { status: 'loading' } | { status: 'ready'; data: RLExplanation } | { status: 'error'; error: unknown }>({ status: 'idle' });
  const ranked = rankQValues(rec.top_actions);
  const explain = async () => {
    setExp({ status: 'loading' });
    try { setExp({ status: 'ready', data: await api().recommendationExplanation(rec.id) }); }
    catch (error) { setExp({ status: 'error', error }); }
  };
  return (
    <li className="rounded-md border border-line bg-panel-2 p-3" data-testid={`live-defense-rec-${rec.id}`}>
      <p className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-semibold">{actionInWords(rec.action, rec.node)}</span>
        {rec.node && <Tag>{rec.node}</Tag>}
        <span className="text-xs text-muted">Q-margin {num(rec.q_margin, 3)}</span>
      </p>
      <p className="mt-1 text-xs text-muted">policy <Mono>{rec.policy_version}</Mono> · checkpoint <Mono>{rec.checkpoint_sha256.slice(0, 12)}</Mono> · <Time iso={rec.created_at} /></p>
      <p className="mt-1 text-xs text-warn">{rec.caveat || SIMULATION_CAVEAT}</p>
      <div className="mt-3">
        <p className="label-mono mb-2 text-xs">Stored action scores (not live confidence)</p>
        <QRanking actions={ranked} sample={false} />
      </div>
      {exp.status === 'idle' && <Button className="mt-3 !px-2 !py-0.5 text-xs" onClick={() => void explain()}>Load stored explanation</Button>}
      {exp.status === 'loading' && <Loading label="Loading explanation" />}
      {exp.status === 'error' && <ErrorState error={exp.error} onRetry={() => void explain()} context="Explanation" />}
      {exp.status === 'ready' && (
        <div className="mt-3 text-xs">
          <p className="text-muted">Method {exp.data.method} · runner-up {exp.data.runner_up ?? '—'} · margin {num(exp.data.margin, 3)}</p>
          <p className="mt-1 text-warn">{exp.data.caveat}</p>
          <ul className="mt-2">
            {exp.data.top_contributions.map((item, index) => (
              <li key={`${item.feature}-${index}`} className={item.delta_margin > 0 ? 'text-ok' : 'text-bad'}>
                {item.delta_margin > 0 ? 'supports' : 'opposes'} · <Mono>{item.node ? `${item.node}.` : ''}{item.feature}</Mono> = {num(item.value, 3)} (Δmargin {num(item.delta_margin, 3)}, {item.kind})
              </li>
            ))}
          </ul>
        </div>
      )}
    </li>
  );
}

function PreviewExplain() {
  const rec = PREVIEW_RECOMMENDATIONS[0];
  if (!rec) return <Empty>No sample recommendation fixture.</Empty>;
  return (
    <div className="flex flex-col gap-4" data-testid="live-defense-preview-explain">
      <Panel title="Sample explainability chrome" actions={<SourceTag mode="layout-preview" />}>
        <SimulationCaveat text={rec.caveat} />
        <p className="mt-3 text-sm">{actionInWords(rec.action, rec.node)}</p>
        <p className="mt-1 text-xs text-muted">policy <Mono>{rec.policy_version}</Mono> · sample Q-margin {num(rec.q_margin, 3)}</p>
        <div className="mt-3">
          <p className="label-mono mb-2 text-xs">Sample action scores (not a loaded policy)</p>
          <QRanking actions={rec.top_actions} sample />
        </div>
        <ul className="mt-3 text-xs">
          {rec.contributions.map(item => (
            <li key={item.feature} className={item.delta_margin > 0 ? 'text-ok' : 'text-bad'}>
              {item.delta_margin > 0 ? 'supports' : 'opposes'} · <Mono>{item.node ? `${item.node}.` : ''}{item.feature}</Mono> Δmargin {num(item.delta_margin, 3)} ({item.kind})
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}
