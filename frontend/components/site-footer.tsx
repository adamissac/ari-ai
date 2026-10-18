'use client';

import { usePathname } from 'next/navigation';
import { BRAND_TAGLINE, Wordmark } from '@/components/brand';
import { useAuthStageShowing } from '@/lib/auth-stage-presence';

/** Routes where every number really is read from saved records or the committed RL bundle. */
export function showsRecordsFooter(pathname: string): boolean {
  return pathname === '/lab' || pathname.startsWith('/lab/') || pathname === '/projects' || pathname.startsWith('/projects/');
}

/**
 * The records-only promise holds for the console and the Defense Lab only. Marketing
 * pages (landing illustrations, pricing) do not get it, because it would be false there,
 * and neither does a sign-in screen (signed-out /projects shows no records).
 * No links here: the header already carries navigation.
 */
export function SiteFooter() {
  const pathname = usePathname();
  const signingIn = useAuthStageShowing();
  if (signingIn || !showsRecordsFooter(pathname)) return null;
  return (
    <footer className="night-footer mx-auto max-w-7xl px-4 pb-12 pt-10" data-testid="site-footer">
      <div className="flex flex-wrap items-center justify-between gap-x-8 gap-y-3">
        <Wordmark className="text-ink" />
        <p className="text-sm text-muted">{BRAND_TAGLINE}</p>
      </div>
      <p className="label-mono mt-6 max-w-4xl leading-relaxed text-faint">Every number here comes from saved records. Nothing is made up in your browser.</p>
    </footer>
  );
}
