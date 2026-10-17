'use client';

import type { BehavioralExpectation, ExpectationStatus } from '@hackatl/frontend-transport';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { Badge, ErrorState, Loading, Mono } from '@/components/ui';
import { api } from '@/lib/api';
import { matchExpectationStatements } from '@/lib/expectations';
import { EXPECTATION_STATUS } from '@/lib/status';

type Load =
  | { status: 'loading' }
  | { status: 'none' }
  | { status: 'ready'; rows: ReturnType<typeof matchExpectationStatements> }
  | { status: 'error'; error: unknown };

const PAGE_LIMIT = 5;

/** Statements for the finding's expectation ids. Ids with no indexed row stay as ids. */
export function ExpectationLinks({ projectId, snapshotId, assessmentId, ids }: {
  projectId: string;
  snapshotId: string | null;
  assessmentId: string;
  ids: readonly string[];
}) {
  const [state, setState] = useState<Load>({ status: 'loading' });
  const [nonce, setNonce] = useState(0);
  const idKey = ids.join('\n');

  useEffect(() => {
    const wanted = idKey === '' ? [] : idKey.split('\n');
    if (wanted.length === 0) return;
    const controller = new AbortController();
    const signal = controller.signal;
    (async () => {
      let snapshot = snapshotId;
      if (!snapshot) {
        const detail = await api().assessment(assessmentId, { signal });
        snapshot = detail.assessment.snapshot_id;
      }
      if (!snapshot) {
        setState({ status: 'none' });
        return;
      }
      const items: BehavioralExpectation[] = [];
      let cursor: string | undefined;
      for (let page = 0; page < PAGE_LIMIT; page += 1) {
        const result = await api().expectations(snapshot, { limit: 500, cursor }, { signal });
        items.push(...result.items);
        if (!result.next_cursor) break;
        cursor = result.next_cursor;
      }
      setState({ status: 'ready', rows: matchExpectationStatements(wanted, items) });
    })().catch((error: unknown) => {
      if (!signal.aborted) setState({ status: 'error', error });
    });
    return () => controller.abort();
  }, [assessmentId, idKey, nonce, snapshotId]);

  if (ids.length === 0) return <p className="text-xs text-faint">No expectation linked to this finding.</p>;
  if (state.status === 'loading') return <Loading label="Loading expectations" />;
  if (state.status === 'error') return <ErrorState error={state.error} onRetry={() => setNonce(n => n + 1)} context="Expectations" />;
  if (state.status === 'none') {
    return (
      <p className="text-xs text-muted">
        This finding has no indexed snapshot, so only the ids are known.{' '}
        {ids.map(id => <Mono key={id}>{id} </Mono>)}
      </p>
    );
  }
  return (
    <ul className="flex flex-col gap-2" data-testid="finding-expectations">
      {state.rows.map(row => (
        <li key={row.id}>
          {row.statement ? (
            <>
              <p className="text-sm text-ink">{row.statement}</p>
              <p className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-muted">
                {row.status && row.status in EXPECTATION_STATUS && <Badge view={EXPECTATION_STATUS[row.status as ExpectationStatus]} />}
                <Mono>{row.id}</Mono>
                <Link className="text-accent hover:underline" href={`/projects/${projectId}/expectations`}>Review on the expectations page</Link>
              </p>
            </>
          ) : (
            <p className="text-xs text-muted">No statement in the indexed snapshot for <Mono>{row.id}</Mono>.</p>
          )}
        </li>
      ))}
    </ul>
  );
}
