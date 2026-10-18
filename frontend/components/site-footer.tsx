'use client';

import { usePathname } from 'next/navigation';
import { useAuthStageShowing } from '@/lib/auth-stage-presence';

/** Routes where every number really is read from saved records or the committed RL bundle. */
export function showsRecordsFooter(pathname: string): boolean {
  return pathname === '/lab' || pathname.startsWith('/lab/') || pathname === '/projects' || pathname.startsWith('/projects/');
}

/**
 * The records-only promise holds for the console and the Defense Lab only. Marketing
 * pages (landing illustrations, pricing) do not get it, because it would be false there,
 * and neither does a sign-in screen (signed-out /projects shows no records).
 */
export function SiteFooter() {
  const pathname = usePathname();
  const signingIn = useAuthStageShowing();
  if (signingIn || !showsRecordsFooter(pathname)) return null;
  return (
    <footer className="label-mono mx-auto max-w-7xl border-t border-line px-4 py-6 text-faint" data-testid="site-footer">
      Every number here comes from saved records. Nothing is made up in your browser.
    </footer>
  );
}
