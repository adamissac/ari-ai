'use client';

import type { AnalystReview, AnalystReviewCreate } from '@hackatl/frontend-transport';
import { useState } from 'react';
import { Button, ErrorState, Field, inputClass, Mono, Tag, Time } from '@/components/ui';
import { api } from '@/lib/api';

const DECISIONS: AnalystReviewCreate['decision'][] = ['accept', 'reject', 'needs_investigation'];

export function AnalystReviewForm({
  recommendationId,
  history,
  onSaved,
}: {
  recommendationId: string;
  history: AnalystReview[];
  onSaved?: () => void;
}) {
  const [decision, setDecision] = useState<AnalystReviewCreate['decision']>('needs_investigation');
  const [reason, setReason] = useState('');
  const [status, setStatus] = useState<'idle' | 'saving' | 'error'>('idle');
  const [error, setError] = useState<unknown>(null);
  const submit = async () => {
    setStatus('saving');
    setError(null);
    try {
      await api().createRecommendationReview(recommendationId, {
        decision,
        reason: reason.trim() ? reason.trim() : null,
      });
      setReason('');
      setStatus('idle');
      onSaved?.();
    } catch (err) {
      setError(err);
      setStatus('error');
    }
  };
  return (
    <div className="mt-4 border-t border-line pt-3" data-testid={`live-defense-review-${recommendationId}`}>
      <p className="text-sm font-medium text-ink">Analyst review</p>
      <p className="mt-1 text-xs text-muted">
        Accept records your opinion only. It does not apply a control, start an adapter, or replace a two-person incident approval.
      </p>
      <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-end">
        <Field label="Decision">
          <select className={inputClass} value={decision} onChange={e => setDecision(e.target.value as AnalystReviewCreate['decision'])}>
            {DECISIONS.map(item => <option key={item} value={item}>{item.replaceAll('_', ' ')}</option>)}
          </select>
        </Field>
        <Field label="Reason (optional)">
          <input className={inputClass} value={reason} onChange={e => setReason(e.target.value)} maxLength={500} />
        </Field>
        <Button className="sm:mb-0.5" disabled={status === 'saving'} onClick={() => void submit()}>
          Record review
        </Button>
      </div>
      {status === 'error' && error !== null && <div className="mt-2"><ErrorState error={error} onRetry={() => void submit()} context="Review" /></div>}
      <h4 className="label-mono mt-3 text-xs text-ink">History</h4>
      {history.length === 0 ? <p className="mt-1 text-xs text-muted">No reviews recorded.</p> : (
        <ol className="mt-1 flex flex-col gap-1">
          {history.map(item => (
            <li key={item.id} className="text-xs text-ink">
              <Tag tone={item.decision === 'accept' ? 'ok' : item.decision === 'reject' ? 'bad' : 'warn'}>{item.decision.replaceAll('_', ' ')}</Tag>
              {' '}
              <Time iso={item.reviewed_at} /> · <Mono>{item.reviewed_by}</Mono>
              {item.reason ? ` — ${item.reason}` : ''}
              {item.executes === false && <span className="text-muted"> · did not execute</span>}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
