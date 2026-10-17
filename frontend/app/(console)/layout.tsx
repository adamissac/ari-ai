'use client';

import { usePathname } from 'next/navigation';
import type { ReactNode } from 'react';
import { SessionGate } from '@/components/session';
import { UserBar } from '@/components/user-bar';

export default function ConsoleLayout({ children }: { children: ReactNode }) {
  // The home page opens on a full-screen hero and renders its own UserBar below it.
  const home = usePathname() === '/';
  return (
    <SessionGate>
      {!home && <UserBar />}
      {children}
    </SessionGate>
  );
}
