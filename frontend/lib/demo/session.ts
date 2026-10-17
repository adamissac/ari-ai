'use client';

import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';
import { DEMO_USER, type DemoUser } from '@/lib/demo/data';

/**
 * The demo account's session. Signing in happens on /access with an access code checked on
 * the server, which sets an httpOnly cookie; proxy.ts keeps /demo closed without it. This
 * hook only asks the server whether that cookie is valid. No GitHub OAuth happens here.
 */
export function useDemoSession(): { user: DemoUser | null; ready: boolean; signOut: () => void } {
  const router = useRouter();
  const [user, setUser] = useState<DemoUser | null>(null);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/demo-session', { signal: controller.signal, cache: 'no-store' })
      .then(r => r.json() as Promise<{ signedIn?: boolean }>)
      .then(body => { setUser(body.signedIn ? DEMO_USER : null); setReady(true); })
      .catch(() => { if (!controller.signal.aborted) { setUser(null); setReady(true); } });
    return () => controller.abort();
  }, []);
  const signOut = useCallback(() => {
    fetch('/api/demo-session', { method: 'DELETE' })
      .catch(() => { /* the cookie expires on its own */ })
      .finally(() => { setUser(null); router.push('/'); });
  }, [router]);
  return { user, ready, signOut };
}
