'use client';

import Link from 'next/link';
import { Term } from '@/components/term';
import type { LoopNode, LoopTone } from '@/lib/pillars';

const TONE: Record<LoopTone, { ring: string; dot: string; word: string }> = {
  good: { ring: 'border-ok/40', dot: 'bg-ok', word: 'OK' },
  attention: { ring: 'border-warn/60', dot: 'bg-warn', word: 'Needs a look' },
  active: { ring: 'border-info/40', dot: 'bg-info', word: 'In progress' },
  empty: { ring: 'border-line', dot: 'bg-faint', word: 'Nothing yet' },
  unknown: { ring: 'border-bad/40', dot: 'bg-bad', word: 'Not loaded' },
};

/**
 * The three pillars as one connected loop. Arrows show what each step feeds into;
 * the return arrow is the monitoring re-check. Status words come from records.
 */
export function PillarLoop({ nodes }: { nodes: LoopNode[] }) {
  return (
    <section aria-labelledby="loop-title" className="rounded-xl border border-line bg-panel p-5" data-testid="pillar-loop">
      <h2 id="loop-title" className="text-lg font-semibold tracking-tight">How the three parts work together</h2>
      <p className="mt-1 max-w-3xl text-sm text-muted">
        Each step hands its results to the next. When the code changes, <Term t="monitoring">monitoring</Term> starts the loop again.
        The status in each box is read from this project&apos;s records.
      </p>
      <ol className="mt-4 grid gap-2 md:grid-cols-5" aria-label="Product loop">
        {nodes.map((n, i) => {
          const tone = TONE[n.tone];
          return (
            <li key={n.id} className="relative flex" data-testid={`loop-${n.id}`}>
              <Link href={n.href} className={`flex w-full flex-col rounded-lg border-2 ${tone.ring} bg-panel-2/60 p-3 transition-colors hover:bg-panel-2`}>
                <span className="label-mono text-faint">{String(i + 1).padStart(2, '0')} · {n.pillar}</span>
                <span className="mt-1 font-semibold">{n.title}</span>
                <span className="mt-0.5 text-xs italic text-muted">{n.question}</span>
                <span className="mt-2 flex items-start gap-1.5 text-sm">
                  <span aria-hidden="true" className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${tone.dot}`} />
                  <span><span className="sr-only">{tone.word}: </span>{n.status}</span>
                </span>
              </Link>
              {i < nodes.length - 1 && (
                <span aria-hidden="true" className="absolute -bottom-2.5 left-1/2 z-10 -translate-x-1/2 text-faint md:-right-2.5 md:bottom-auto md:left-auto md:top-1/2 md:-translate-y-1/2 md:translate-x-0">
                  <span className="md:hidden">↓</span><span className="hidden md:inline">→</span>
                </span>
              )}
            </li>
          );
        })}
      </ol>
      <p className="mt-2 flex items-center gap-2 text-xs text-muted" data-testid="loop-return">
        <span aria-hidden="true" className="text-base text-brand">↺</span>
        A new code change sends the loop back to step 01: the changed code is understood, reviewed and tested again.
      </p>
      <Link href="/lab" className="mt-3 flex flex-wrap items-center gap-2 rounded-lg border border-dashed border-line p-3 text-sm hover:bg-panel-2" data-testid="loop-lab">
        <span className="label-mono text-faint">Research · simulation only</span>
        <span className="font-semibold">Defense Lab</span>
        <span className="text-muted">An AI defender practising against simulated attacks. It explores how step 05 could respond in future; it never acts on real systems.</span>
      </Link>
    </section>
  );
}
