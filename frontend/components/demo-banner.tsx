'use client';

import { useRouter } from 'next/navigation';
import { resetDemoSimulation } from '@/lib/demo/console/state';
import { useDemoView } from '@/lib/demo/use-view';

export function DemoBanner() {
  const router = useRouter();
  const active = useDemoView();
  const exitDemo = async () => {
    await fetch('/api/demo-session', { method: 'DELETE', cache: 'no-store' });
    resetDemoSimulation();
    router.push('/');
  };
  if (!active) return null;
  return (
    <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2 border-b border-brand/30 bg-bg/95 px-4 py-2 text-sm leading-snug text-muted">
      <p className="min-w-0 text-center">Demo account · Lumen Pay sample data. Ari reviews each commit, seven security agents try to break it, a person approves the fix, and an independent check proves it. Every repository, commit and result here is illustrative.</p>
      <button type="button" className="font-semibold text-brand hover:text-brand-deep" onClick={() => void exitDemo()}>
        Exit demo
      </button>
    </div>
  );
}
