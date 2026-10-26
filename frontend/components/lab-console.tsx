'use client';

import { useMemo, useState } from 'react';
import { actionInWords } from '@/lib/lab-plain';
import { isDisruptive, parseAction } from '@/lib/lab-story';
import type { LabEpisode, LabScenario } from '@/lib/lab-types';

type ConsoleSideProps = { episode: LabEpisode; scenario: LabScenario; t: number };

export function ConsoleSide({ episode, scenario, t }: ConsoleSideProps) {
  const [decisions, setDecisions] = useState<Record<string, 'approved' | 'dismissed'>>({});
  const activity = useMemo(() => episode.steps
    .filter(step => step.t <= t && parseAction(step.action).verb !== 'noop')
    .slice(-8)
    .reverse(), [episode, t]);
  const actions = useMemo(() => {
    const byAction = new Map<string, { action: string; t: number }>();
    for (const step of episode.steps) {
      if (step.t > t) continue;
      const { verb } = parseAction(step.action);
      if (isDisruptive(verb)) byAction.set(step.action, { action: step.action, t: step.t });
    }
    return [...byAction.values()].sort((a, b) => b.t - a.t);
  }, [episode, t]);
  const waiting = actions.filter(item => !decisions[item.action]);
  const approved = actions.filter(item => decisions[item.action] === 'approved');

  const decide = (action: string, decision: 'approved' | 'dismissed') => {
    setDecisions(current => ({ ...current, [action]: decision }));
  };

  return (
    <div className="flex flex-col gap-6" data-scenario={scenario.name}>
      <section className="border-y border-line" data-testid="lab-console-activity">
        <h3 className="label-mono py-3 text-faint">Activity</h3>
        {activity.length > 0 ? (
          <ul className="divide-y divide-line">
            {activity.map(step => (
              <li key={`${step.t}-${step.action}`} className="flex items-baseline justify-between gap-4 py-2.5 text-sm">
                <span className="label-mono shrink-0 text-faint">step {step.t}</span>
                <span className="min-w-0 text-right text-ink">{actionInWords(step.action)}</span>
              </li>
            ))}
          </ul>
        ) : <p className="py-3 text-sm text-muted">Nothing recorded yet.</p>}
      </section>

      <section className="border-y border-line" aria-labelledby="approval-title">
        <h3 id="approval-title" className="label-mono py-3 text-faint">Waiting for your approval</h3>
        {waiting.length > 0 ? (
          <ul className="divide-y divide-line">
            {waiting.map(item => (
              <li key={item.action} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 py-3">
                <span className="min-w-0 text-sm text-ink">{actionInWords(item.action)}</span>
                <span className="flex shrink-0 gap-4 text-xs">
                  <button type="button" className="font-medium text-ok hover:underline" onClick={() => decide(item.action, 'approved')}>Approve</button>
                  <button type="button" className="font-medium text-muted hover:text-ink" onClick={() => decide(item.action, 'dismissed')}>Dismiss</button>
                </span>
              </li>
            ))}
          </ul>
        ) : <p className="py-3 text-sm text-muted">Nothing waiting.</p>}
        {approved.length > 0 && (
          <ul className="divide-y divide-line" aria-label="Demo-only approval decisions">
            {approved.map(item => (
              <li key={item.action} className="space-y-1 py-3 text-sm">
                <p className="text-ink">{actionInWords(item.action)}</p>
                <p className="text-muted">Approved · demo only, nothing was changed</p>
              </li>
            ))}
          </ul>
        )}
        <p className="border-t border-line py-3 text-xs text-faint">In this recorded run, approving only updates this screen.</p>
      </section>
    </div>
  );
}
