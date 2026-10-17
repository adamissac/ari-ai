'use client';

import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { useDemoSession } from '@/lib/demo/session';

/** Pages past the demo sign-in send a signed-out visitor back to it. */
export function useDemoGate(): ReturnType<typeof useDemoSession> {
  const session = useDemoSession();
  const router = useRouter();
  useEffect(() => {
    if (session.ready && !session.user) router.replace('/demo');
  }, [session.ready, session.user, router]);
  return session;
}
