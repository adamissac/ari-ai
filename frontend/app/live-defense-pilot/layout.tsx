'use client';

import { Suspense, type ReactNode } from 'react';
import { LiveDefenseShell } from '@/components/live-defense/shell';
import { Loading } from '@/components/ui';

/** Isolated sample layout. No session, no control-plane calls. */
export default function PilotLayout({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <Suspense fallback={<Loading label="Loading sample layout" />}>
        <LiveDefenseShell projectId={null} standalone>{children}</LiveDefenseShell>
      </Suspense>
    </div>
  );
}
