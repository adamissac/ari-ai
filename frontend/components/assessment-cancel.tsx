'use client';
import { useState } from 'react';
import { Button, ErrorState } from '@/components/ui';
import { api } from '@/lib/api';
import { CANCEL_ASSESSMENT_NOTE, cancelAssessmentResult } from '@/lib/cancel-assessment';

export function CancelButton({ id, onDone, compact = false }: { id: string; onDone: () => void; compact?: boolean }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [result, setResult] = useState<string | null>(null);
  return (
    <div className="flex max-w-sm flex-col items-end gap-1">
      <Button variant="danger" disabled={busy} onClick={async () => {
        setBusy(true);
        setError(null);
        setResult(null);
        try {
          const response = await api().cancelAssessment(id);
          setResult(cancelAssessmentResult(response.cancelled));
          onDone();
        } catch (err) { setError(err); } finally { setBusy(false); }
      }}>Cancel assessment</Button>
      {compact ? <details className="text-xs text-muted"><summary>About cancellation</summary><p className="mt-2" data-testid="cancel-assessment-note">{CANCEL_ASSESSMENT_NOTE}</p></details> : <p className="text-right text-xs text-muted" data-testid="cancel-assessment-note">{CANCEL_ASSESSMENT_NOTE}</p>}
      {result !== null && <p className="text-right text-xs text-ink" data-testid="cancel-assessment-result" role="status">{result}</p>}
      {error !== null && <ErrorState error={error} context="Cancel" />}
    </div>
  );
}

