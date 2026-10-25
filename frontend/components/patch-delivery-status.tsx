'use client';

import type { PatchDelivery } from '@hackatl/frontend-transport';
import { Badge, Mono } from '@/components/ui';
import { shortSha } from '@/lib/format';

export function PatchDeliveryStatus({
  patchId,
  delivery,
}: {
  patchId: string;
  delivery: PatchDelivery | null;
}) {
  if (!delivery) return null;

  return (
    <div className="mt-2 flex flex-wrap items-center gap-2 text-xs" data-testid={`patch-delivery-${patchId}`}>
      {delivery.status === 'pr_opened' && (
        <>
          <Badge view={{ label: 'Pull request opened', tone: 'ok', glyph: '↗' }} />
          {delivery.url && <a className="text-accent hover:underline" href={delivery.url} rel="noreferrer" target="_blank">Open pull request</a>}
          {delivery.branch && <span>Branch <Mono>{delivery.branch}</Mono></span>}
        </>
      )}
      {delivery.status === 'pushed' && (
        <>
          <Badge view={{ label: `Committed to ${delivery.branch ?? 'the default branch'}`, tone: 'ok', glyph: '✓' }} />
          {delivery.commit_sha && <Mono>{shortSha(delivery.commit_sha)}</Mono>}
        </>
      )}
      {delivery.status === 'pending' && (
        <Badge view={{ label: 'Delivering the verified fix…', tone: 'warn', glyph: '…' }} />
      )}
      {delivery.status === 'failed' && (
        <>
          <Badge view={{ label: `Delivery failed: ${delivery.reason ?? 'unknown reason'}`, tone: 'bad', glyph: '×' }} />
          <span className="text-muted">Ari didn&apos;t change your repository.</span>
        </>
      )}
      {delivery.status === 'skipped' && (
        <Badge view={{ label: 'Not delivered: delivery is manual', tone: 'neutral', glyph: '—' }} />
      )}
    </div>
  );
}
