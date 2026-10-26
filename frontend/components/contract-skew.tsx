'use client';

import { useEffect, useState } from 'react';
import { CONTRACT_SCHEMA_VERSION } from '../../shared/generated/ts/contracts';

type Skew = { kind: 'reload'; backend: string } | { kind: 'same' } | null;

/**
 * Strict contract decoding rejects a response from a backend on a different contract than this
 * page was built for (an open tab from before a deploy, or a backend shipped ahead of the
 * frontend). Say which, so the person can reload instead of facing a dead error.
 */
export function ContractSkewHint() {
  const [skew, setSkew] = useState<Skew>(null);
  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/frontend-version', { cache: 'no-store', signal: controller.signal })
      .then(r => r.json() as Promise<{ backend: { schemaVersion: string | null } | null; frontend: { schemaVersion: string | null } }>)
      .then(pair => {
        const served = [pair.backend?.schemaVersion, pair.frontend.schemaVersion].find(v => v && v !== CONTRACT_SCHEMA_VERSION);
        setSkew(served ? { kind: 'reload', backend: served } : pair.backend?.schemaVersion ? { kind: 'same' } : null);
      })
      .catch(() => { /* no hint; the error above still stands */ });
    return () => controller.abort();
  }, []);
  if (skew?.kind === 'reload') {
    return (
      <p className="mt-2 text-sm" data-testid="contract-skew">
        Ari was updated since this page loaded (contract {CONTRACT_SCHEMA_VERSION} here, {skew.backend} now).{' '}
        <button type="button" className="font-semibold text-brand underline-offset-2 hover:underline" onClick={() => window.location.reload()}>Reload the page</button>
      </p>
    );
  }
  if (skew?.kind === 'same') return <p className="mt-1 text-xs text-faint" data-testid="contract-skew">Frontend and backend both run contract {CONTRACT_SCHEMA_VERSION}, so this is a real mismatch. Please report it with the time it happened.</p>;
  return null;
}
