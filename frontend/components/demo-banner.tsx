'use client';

import { useCallback, useSyncExternalStore } from 'react';
import { usePathname, useRouter } from 'next/navigation';

export function DemoBanner() {
  const pathname = usePathname();
  const router = useRouter();
  const exitDemo = async () => {
    await fetch('/api/demo-session', { method: 'DELETE', cache: 'no-store' });
    router.push('/');
  };
  const subscribe = useCallback((onChange: () => void) => {
    void pathname;
    window.addEventListener('ari-demo-session-changed', onChange);
    return () => window.removeEventListener('ari-demo-session-changed', onChange);
  }, [pathname]);
  const active = useSyncExternalStore(subscribe, () => document.cookie.split(';').some(cookie => cookie.trim() === 'ari_demo_view=1'), () => false);

  if (!active) return null;
  return (
    <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2 border-b border-brand/30 bg-bg/95 px-4 py-2 text-sm text-muted">
      <p>Demo account · Lumen Pay sample data — every repository, commit and result here is illustrative.</p>
      <button type="button" className="font-semibold text-brand hover:text-brand-deep" onClick={() => void exitDemo()}>
        Exit demo
      </button>
    </div>
  );
}
