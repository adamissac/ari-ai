'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

export type Resource<T> =
  | { status: 'loading'; data: undefined; error: undefined; reload: () => void }
  | { status: 'ready'; data: T; error: undefined; reload: () => void }
  | { status: 'error'; data: undefined; error: unknown; reload: () => void };

/**
 * Fetch on mount and whenever `key` changes. Earlier requests are aborted so a
 * slow stale response can never overwrite a newer one. `pollMs` refreshes in
 * place (keeps the last good data visible while it reloads).
 */
export function useResource<T>(key: string | null, load: (signal: AbortSignal) => Promise<T>, pollMs?: number): Resource<T> {
  const [state, setState] = useState<{ status: 'loading' | 'ready' | 'error'; data?: T; error?: unknown }>({ status: 'loading' });
  const [nonce, setNonce] = useState(0);
  const loadRef = useRef(load);
  useEffect(() => { loadRef.current = load; });
  const reload = useCallback(() => setNonce(n => n + 1), []);

  useEffect(() => {
    if (key === null) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    const run = (first: boolean) => {
      if (first) setState(s => (s.status === 'ready' ? s : { status: 'loading' }));
      loadRef.current(controller.signal).then(
        data => {
          if (controller.signal.aborted) return;
          setState({ status: 'ready', data });
          if (pollMs) timer = setTimeout(() => run(false), pollMs);
        },
        (error: unknown) => {
          if (controller.signal.aborted) return;
          setState({ status: 'error', error });
        },
      );
    };
    run(true);
    return () => { controller.abort(); if (timer) clearTimeout(timer); };
  }, [key, nonce, pollMs]);

  if (state.status === 'ready') return { status: 'ready', data: state.data as T, error: undefined, reload };
  if (state.status === 'error') return { status: 'error', data: undefined, error: state.error, reload };
  return { status: 'loading', data: undefined, error: undefined, reload };
}
