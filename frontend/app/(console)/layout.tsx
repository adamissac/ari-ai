'use client';

import { usePathname } from 'next/navigation';
import type { ReactNode } from 'react';
import { SessionGate } from '@/components/session';
import { UserBar } from '@/components/user-bar';
import { DEMO_ONLY } from '@/lib/deployment';

export default function ConsoleLayout({ children }: { children: ReactNode }) {
  // The home page opens on a full-screen hero and renders its own UserBar below it.
  const home = usePathname() === '/';
  // Without a backend the landing page still renders; console routes redirect to /demo.
  if (DEMO_ONLY && home) return <>{children}</>;
  return (
    <SessionGate>
      {!home && <UserBar />}
      {children}
    </SessionGate>
  );
}
