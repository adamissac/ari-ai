'use client';
import type { Approval, StreamEvent } from '@hackatl/frontend-transport';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSession } from '@/components/session';
import { Badge, Button, Empty, ErrorState, Loading, Mono, Panel, Time } from '@/components/ui';
import { api } from '@/lib/api';
import { useActionKeys } from '@/lib/action-key';
import { APPROVAL_STATUS } from '@/lib/status';

export function ApprovalGate({ projectId, events, onDecided }: { projectId: string; events: StreamEvent[]; onDecided: () => void }) {
  const { me } = useSession();
  const [approvals, setApprovals] = useState<Approval[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const requested = useMemo(() => new Set(events.map(e => e.approval_id).filter((x): x is string => !!x)), [events]);
  const load = useCallback(() => {
    api().pendingApprovals(projectId).then(p => setApprovals(p.items.filter(a => requested.has(a.id))), setError);
  }, [projectId, requested]);
  useEffect(load, [load]);
  const keys = useActionKeys('decide-approval');
  const decide = async (ap: Approval, decision: 'approved' | 'declined') => {
    setBusy(true);
    setError(null);
    try { await api().decideApproval(ap.id, { decision, reason: null }, { idempotencyKey: keys.keyFor(`${ap.id}|${decision}`) }); keys.done(); onDecided(); load(); }
    catch (err) { setError(err); } finally { setBusy(false); }
  };
  return (
    <Panel title="Human approval required" className="mt-4 border-warn/50">
      <p className="text-sm text-muted">Approve a candidate fix in an isolated copy. Verify will retest it; nothing is merged or deployed.</p>
      {approvals === null && !error && <Loading label="Loading approval" />}
      {approvals?.length === 0 && <Empty>No pending approval found for this run.</Empty>}
      {approvals?.map((ap, index) => (
        <div key={ap.id} className="mt-3 rounded-lg border border-line p-3 text-sm">
          <p className="mb-3 font-medium">Fix request {index + 1}</p>
          <div className="flex flex-wrap items-center gap-2">
          <Badge view={APPROVAL_STATUS[ap.status]} />
          <Button variant="primary" disabled={busy || ap.requested_by === me.user.id} onClick={() => void decide(ap, 'approved')}>Approve remediation</Button>
          <Button variant="danger" disabled={busy} onClick={() => void decide(ap, 'declined')}>Decline</Button>
          </div>
          <details className="mt-3 text-xs text-muted"><summary>Request details</summary><p className="mt-2 break-all"><Mono>{ap.subject_type}:{ap.subject_id}</Mono></p><p>Requested by {ap.requested_by ?? 'system'} <Time iso={ap.requested_at} /></p></details>
        </div>
      ))}
      {error !== null && <div className="mt-2"><ErrorState error={error} context="Approval" /></div>}
    </Panel>
  );
}

