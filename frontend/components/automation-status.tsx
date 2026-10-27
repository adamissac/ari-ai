'use client';

import type { AutomationStatus as Status } from '@hackatl/frontend-transport';
import { useEffect } from 'react';
import { api } from '@/lib/api';
import { useResource } from '@/lib/use-resource';

const LABEL: Record<Status['state'], string> = { ready: 'Ready', off: 'Off', blocked: 'Blocked' };
const DOT: Record<Status['state'], string> = { ready: 'bg-ok', off: 'bg-faint', blocked: 'bg-warn' };

/**
 * One derived answer to "will Ari review the next push?", from the server's view of every gate
 * (repository switch, project monitoring, change types, scope, quota, GitHub access).
 */
export function AutomationStatus({ repoId, manageHref }: { repoId: string; manageHref?: string }) {
  const status = useResource(`automation-status:${repoId}`, signal => api().automationStatus(repoId, { signal }), 30000);
  const reload = status.reload;
  useEffect(() => {
    window.addEventListener('ari:automation-changed', reload);
    return () => window.removeEventListener('ari:automation-changed', reload);
  }, [reload]);
  if (status.status === 'loading') return <span className="text-xs text-muted">Automatic reviews…</span>;
  if (status.status === 'error') return <span className="text-xs text-warn" data-testid="automation-status">Automatic reviews: unknown (could not check)</span>;
  const { state, reasons } = status.data;
  return (
    <details className="relative text-xs text-muted" data-testid="automation-status" data-state={state}>
      <summary className="flex cursor-pointer list-none items-center gap-2">
        <span aria-hidden="true" className={`h-2 w-2 rounded-full ${DOT[state]}`} />
        Automatic reviews: {LABEL[state]}
        {status.refreshError !== undefined && <span className="text-warn">(not refreshed)</span>}
      </summary>
      <div className="absolute right-0 z-20 mt-2 w-72 rounded-lg border border-line bg-panel p-3 text-left shadow-lg">
        {reasons.length === 0
          ? <p>A new push or pull request on this repository will be reviewed.</p>
          : <ul className="list-disc space-y-1 pl-4">{reasons.map(reason => <li key={reason.code}>{reason.message}</li>)}</ul>}
        {manageHref && <a className="mt-2 inline-block font-semibold text-brand hover:underline" href={manageHref}>Manage repositories →</a>}
      </div>
    </details>
  );
}
