'use client';

import { useEffect, useSyncExternalStore } from 'react';

/**
 * Whether a sign-in screen (components/auth-stage.tsx) is on the page. The root layout's
 * records footer reads it: a sign-in screen shows no records, so the footer's promise
 * ("every number here comes from saved records") must not render under it.
 */
let mounted = 0;
const listeners = new Set<() => void>();

function emit() {
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Call from the sign-in screen: marks it present while mounted. */
export function useMarkAuthStage(): void {
  useEffect(() => {
    mounted += 1;
    emit();
    return () => {
      mounted -= 1;
      emit();
    };
  }, []);
}

export function useAuthStageShowing(): boolean {
  return useSyncExternalStore(subscribe, () => mounted > 0, () => false);
}
