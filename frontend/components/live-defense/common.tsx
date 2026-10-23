'use client';

import type { LiveDefenseMode, RankedAction } from '@/lib/live-defense';
import { actionInWords, HEALTH_UNKNOWN_COPY, NO_ENFORCEMENT, OWNED_TEST_AUTHORIZE_COPY, OWNED_TEST_LABEL, SHADOW_MODE_COPY, SIMULATION_CAVEAT } from '@/lib/live-defense';
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
    <p role="status" data-testid="live-defense-preview-banner" className="rounded-xl border border-warn/60 bg-warn/20 px-4 py-3 text-sm font-medium text-warn">
      {PREVIEW_BANNER}
    </p>
  );
}

export function EnforcementNote() {
  return (
    <p data-testid="live-defense-no-enforcement" className="rounded-xl border border-line bg-panel-2 px-4 py-3 text-sm text-ink">
      {NO_ENFORCEMENT}
    </p>
  );
}

export function ShadowModeNote() {
  return (
    <p data-testid="live-defense-shadow-mode" className="rounded-xl border border-line bg-panel-2 px-4 py-3 text-sm text-ink">
      {SHADOW_MODE_COPY}
    </p>
  );
}

export function HealthUnknownNote() {
  return (
    <p data-testid="live-defense-health-unknown" className="text-sm text-ink">
      {HEALTH_UNKNOWN_COPY}
    </p>
  );
}

export function OwnedTestBanner() {
  return (
    <p data-testid="live-defense-owned-test" className="rounded-xl border border-accent/40 bg-accent/10 px-4 py-3 text-sm text-ink">
      <span className="font-semibold">{OWNED_TEST_LABEL}.</span> {OWNED_TEST_AUTHORIZE_COPY}
    </p>
  );
}

export function SimulationCaveat({ text = SIMULATION_CAVEAT }: { text?: string }) {
  return (
    <p data-testid="live-defense-rl-caveat" className="rounded border border-warn/50 bg-warn/15 px-2 py-1.5 text-xs font-medium text-warn">
      {text}
    </p>
  );
}

export function Unavailable({ label }: { label: string }) {
  return <span className="text-muted">{label}: <span className="text-ink">unavailable</span></span>;
}

export function QRanking({ actions, sample }: { actions: readonly RankedAction[]; sample: boolean }) {
  if (actions.length === 0) {
    return <p className="text-sm text-muted">No stored action scores. This panel does not invent a confidence value.</p>;
  }
  return (
    <ol className="ld-q-list" data-testid="live-defense-q-ranking" data-sample={sample ? 'true' : 'false'}>
      {actions.map(item => (
        <li key={`${item.rank}-${item.action}-${item.node ?? 'none'}`}>
          <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm text-ink">
            <span>
              <span className="label-mono text-muted">#{item.rank}</span>{' '}
              {actionInWords(item.action, item.node)}
            </span>
            <Mono>Q {num(item.q_value, 3)}</Mono>
          </div>
          <div className="ld-q-track" aria-hidden="true">
            <span className="ld-q-bar" style={{ width: `${Math.round(item.bar * 100)}%` }} />
          </div>
          <p className="mt-1 text-xs text-muted">Stored Q-value, not a probability and not live confidence.</p>
        </li>
      ))}
    </ol>
  );
}
