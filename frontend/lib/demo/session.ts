'use client';

import { useCallback, useEffect, useState } from 'react';
import { DEMO_USER, type DemoUser } from '@/lib/demo/data';

/** Simulated GitHub sign-in for the demo. No OAuth happens and no token exists. */
const KEY = 'ari-demo-session';

function read(): DemoUser | null {
  try {
    return window.sessionStorage.getItem(KEY) ? DEMO_USER : null;
  } catch {
    return null;
  }
}

export function useDemoSession(): { user: DemoUser | null; ready: boolean; signIn: () => void; signOut: () => void } {
  const [user, setUser] = useState<DemoUser | null>(null);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    // Storage is only readable after mount; the first render is the signed-out shell.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setUser(read());
    setReady(true);
  }, []);
  const signIn = useCallback(() => {
    try { window.sessionStorage.setItem(KEY, '1'); } catch { /* storage unavailable: session lasts for this page */ }
    setUser(DEMO_USER);
  }, []);
  const signOut = useCallback(() => {
    try { window.sessionStorage.removeItem(KEY); } catch { /* storage unavailable */ }
    setUser(null);
  }, []);
  return { user, ready, signIn, signOut };
}
