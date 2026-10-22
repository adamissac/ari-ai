'use client';

import type { LiveDefenseMode, RankedAction } from '@/lib/live-defense';
import { actionInWords, NO_ENFORCEMENT, SIMULATION_CAVEAT } from '@/lib/live-defense';
import { PREVIEW_BANNER } from '@/lib/live-defense-preview';
import { num } from '@/lib/format';
import { Mono, Tag } from '@/components/ui';

export function SourceTag({ mode }: { mode: LiveDefenseMode }) {
  return mode === 'layout-preview'
    ? <Tag tone="warn">Sample layout</Tag>
    : <Tag tone="info">Control-plane records</Tag>;
}

export function PreviewBanner() {
  return (
    <p role="status" data-testid="live-defense-preview-banner" className="rounded-xl border border-warn/50 bg-warn/15 px-4 py-3 text-sm font-medium text-warn">
      {PREVIEW_BANNER}
    </p>
  );
}

export function EnforcementNote() {
  return (
    <p data-testid="live-defense-no-enforcement" className="rounded-xl border border-line bg-panel-2 px-4 py-3 text-sm text-muted">
      {NO_ENFORCEMENT}
    </p>
  );
}

export function SimulationCaveat({ text = SIMULATION_CAVEAT }: { text?: string }) {
  return (
    <p data-testid="live-defense-rl-caveat" className="rounded border border-warn/40 bg-warn/10 px-2 py-1.5 text-xs text-warn">
      {text}
    </p>
  );
}

export function QRanking({ actions, sample }: { actions: readonly RankedAction[]; sample: boolean }) {
  if (actions.length === 0) {
    return <p className="text-sm text-muted">No stored action scores. This panel does not invent a confidence value.</p>;
  }
  return (
    <ol className="ld-q-list" data-testid="live-defense-q-ranking" data-sample={sample ? 'true' : 'false'}>
      {actions.map(item => (
        <li key={`${item.rank}-${item.action}-${item.node ?? 'none'}`}>
          <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
            <span>
              <span className="label-mono text-faint">#{item.rank}</span>{' '}
              {actionInWords(item.action, item.node)}
            </span>
            <Mono>Q {num(item.q_value, 3)}</Mono>
          </div>
          <div className="ld-q-track" aria-hidden="true">
            <span className="ld-q-bar" style={{ width: `${Math.round(item.bar * 100)}%` }} />
          </div>
        </li>
      ))}
    </ol>
  );
}
