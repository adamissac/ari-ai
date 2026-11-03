'use client';

import { api } from '@/lib/api';
import { providerNote } from '@/lib/relay';
import { hasNonLiveModelTurns } from '@/lib/status';
import { useResource } from '@/lib/use-resource';

/**
 * Says, on a page reached from outside the run (a finding), when the run that produced it did not
 * use a live model for every model turn. Renders nothing for a live run or while loading; a failed
 * load says the provenance is unknown rather than implying the result is live.
 */
export function RunProvenance({ assessmentId }: { assessmentId: string }) {
  const run = useResource(`run-provenance:${assessmentId}`, s => api().assessment(assessmentId, { signal: s }));
  if (run.status === 'loading') return null;
  if (run.status === 'error') {
    return <p className="mb-4 text-xs text-warn" data-testid="run-provenance">Could not load how the run that produced this was executed, so it is not known whether its model turns were live.</p>;
  }
  const modes = new Map<string, number>();
  for (const r of run.data.agent_runs) modes.set(r.provider_mode, (modes.get(r.provider_mode) ?? 0) + 1);
  if (!hasNonLiveModelTurns(modes.keys())) return null;
  return (
    <p className="mb-4 rounded-md border border-warn/50 bg-warn/10 px-3 py-2 text-sm" data-testid="run-provenance">
      <span className="font-semibold">Not from a live-provider run. </span>
      The run that produced this did not use a live model for every turn, so it demonstrates the workflow rather than a fresh analysis.
      <span className="text-muted"> {providerNote(modes)}</span>
    </p>
  );
}
