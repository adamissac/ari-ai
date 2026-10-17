'use client';

import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { useDemoSession } from '@/lib/demo/session';

/** Demo pages send a visitor without a valid access session to the access-code sign-in. */
export function useDemoGate(): ReturnType<typeof useDemoSession> {
  const session = useDemoSession();
  const router = useRouter();
  useEffect(() => {
    if (session.ready && !session.user) router.replace('/access');
  }, [session.ready, session.user, router]);
  return session;
}
