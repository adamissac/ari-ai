'use client';

import type { AgentName } from '@hackatl/frontend-transport';
import type { RelayItem, RelayStatus } from '@/lib/relay';
import { Term } from '@/components/term';

const LOOK: Record<RelayStatus, { box: string; icon: string }> = {
  done: { box: 'border-ok/50 bg-ok/[0.06]', icon: '✓' },
  running: { box: 'border-info/60 bg-info/[0.06] animate-pulse', icon: '◔' },
  queued: { box: 'border-line bg-panel-2', icon: '○' },
  failed: { box: 'border-bad/60 bg-bad/[0.06]', icon: '×' },
  cancelled: { box: 'border-line bg-panel-2', icon: '■' },
  not_run: { box: 'border-dashed border-line bg-panel', icon: '·' },
};

/**
 * The eight agents as a relay, in the order the orchestrator runs them, with the
 * human approval gate between planning and fixing. Selecting a tile opens that
 * agent's recorded runs below.
 */
export function AgentRelay({ items, selected, onSelect }: { items: RelayItem[]; selected: AgentName; onSelect: (a: AgentName) => void }) {
  const numbers = new Map(items.filter(i => i.kind === 'agent').map((item, i) => [item.kind === 'agent' ? item.agent : '', i + 1]));
  return (
    <section className="agent-journey" aria-labelledby="relay-title" data-testid="agent-relay">
      <h2 id="relay-title" className="text-lg font-semibold tracking-tight">One code reviewer. Seven security agents.</h2>
      <p className="mt-1 max-w-3xl text-sm text-muted">
        Each <Term t="agent">agent</Term> is a separate AI worker with one job. It passes its result to the next one.
        A person must give <Term t="approval">approval</Term> before any fix is built. Select an agent to see exactly what it did.
      </p>
      <div className="journey-lanes" aria-hidden="true"><span><b>01 / REVIEW</b> Does the change work?</span><span><b>02 / SECURITY</b> Can someone break it?</span><span><b>03 / PROOF</b> Did the fix hold up?</span></div>
      <ol className="mt-3 flex flex-col gap-2 lg:flex-row lg:flex-wrap lg:items-stretch">
        {items.map((item, i) => {
          if (item.kind === 'gate') {
            const tone = item.status === 'waiting' ? 'border-warn bg-warn/10 text-warn' : item.status === 'passed' ? 'border-ok/50 text-ok' : 'border-line text-muted';
            return (
              <li key="gate" className={`flex items-center gap-2 rounded-lg border-2 border-dashed px-3 py-2 text-xs lg:w-40 ${tone}`} data-testid="relay-gate" data-status={item.status}>
                <span aria-hidden="true" className="text-lg">✋</span>
                <span><span className="block font-semibold">Human approval</span>{item.text}</span>
              </li>
            );
          }
          const n = numbers.get(item.agent) ?? 0;
          const look = LOOK[item.status];
          const pressed = item.agent === selected;
          const prev = items[i - 1];
          const newStage = !prev || prev.kind === 'gate' || prev.stage !== item.stage;
          return (
            <li key={item.agent} className="flex lg:w-[calc(25%-0.5rem)] xl:w-[calc(20%-0.5rem)]">
              <button
                type="button"
                aria-pressed={pressed}
                onClick={() => onSelect(item.agent)}
                data-testid={`relay-${item.agent}`}
                data-status={item.status}
                data-team={item.agent === 'reviewer' ? 'review' : ['scout', 'probe', 'trace'].includes(item.agent) ? 'challenge' : item.agent === 'verify' ? 'proof' : 'defend'}
                className={`flex w-full flex-col rounded-lg border-2 p-3 text-left transition-shadow ${look.box} ${pressed ? 'ring-2 ring-brand ring-offset-1' : 'hover:shadow-md'}`}
              >
                <span className="label-mono text-faint">{newStage ? item.stage : ' '}</span>
                <span className="mt-1 flex items-center justify-between gap-2">
                  <span className="font-semibold"><span className="text-faint">{n}.</span> {item.label}</span>
                  <span className="flex items-center gap-1 text-xs"><span aria-hidden="true">{look.icon}</span>{item.statusText}</span>
                </span>
                <span className="mt-1 text-xs text-muted">{item.job}</span>
                <span className="mt-2 border-t border-line/70 pt-1.5 text-xs"><span className="text-faint">Handed on: </span>{item.handoff}</span>
              </button>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
