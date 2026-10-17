'use client';

import { useState } from 'react';
import { idempotencyKey } from '@/lib/api';

/**
 * One idempotency key per user action. Retrying the same action (same signature)
 * after a failure reuses its key, so the backend replays instead of duplicating;
 * any change to the inputs, or a success, starts a new action with a new key.
 * Keys are never rotated just because a request failed.
 */
export class ActionKeys {
  private current: { sig: string; key: string; payload?: unknown } | null = null;
  constructor(private readonly prefix: string, private readonly mint: (prefix: string) => string = idempotencyKey) {}
  keyFor(signature: string): string {
    if (this.current?.sig !== signature) this.current = { sig: signature, key: this.mint(this.prefix) };
    return this.current.key;
  }
  /**
   * The request body for this action, built once. A retry must resend the exact same
   * body (e.g. a computed expiry), or the backend rightly rejects the reused key.
   */
  payloadFor<T>(signature: string, build: () => T): T {
    this.keyFor(signature);
    const c = this.current!;
    if (!('payload' in c)) c.payload = build();
    return c.payload as T;
  }
  /** The action succeeded: the next submit is a new action. */
  done(): void { this.current = null; }
}

/** One stable ActionKeys per component instance. */
export function useActionKeys(prefix: string): ActionKeys {
  const [keys] = useState(() => new ActionKeys(prefix));
  return keys;
}
