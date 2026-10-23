'use client';

import { Suspense, type ReactNode } from 'react';
import { LiveDefenseShell } from '@/components/live-defense/shell';
import { useParam } from '@/components/project';
import { Loading } from '@/components/ui';

export default function LiveDefenseLayout({ children }: { children: ReactNode }) {
  const projectId = useParam('projectId');
  return (
    <Suspense fallback={<Loading label="Loading Live Defense" />}>
      <LiveDefenseShell projectId={projectId}>{children}</LiveDefenseShell>
    </Suspense>
  );
}
