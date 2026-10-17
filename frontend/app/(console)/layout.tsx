'use client';

import { usePathname } from 'next/navigation';
import type { ReactNode } from 'react';
import { OptionalSession, SessionGate } from '@/components/session';
import { UserBar } from '@/components/user-bar';
import { DEMO_ONLY } from '@/lib/deployment';

export default function ConsoleLayout({ children }: { children: ReactNode }) {
  // The home page opens on a full-screen hero and renders its own UserBar below it.
  const home = usePathname() === '/';
  // The landing page is public: it never waits for or requires a session.
  // Without a backend it renders as is; console routes redirect to /demo.
  if (home) return DEMO_ONLY ? <>{children}</> : <OptionalSession>{children}</OptionalSession>;
  return (
    <SessionGate>
      {!home && <UserBar />}
      {children}
    </SessionGate>
  );
}
