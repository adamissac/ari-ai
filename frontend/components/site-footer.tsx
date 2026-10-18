'use client';

import { usePathname } from 'next/navigation';
import { BRAND_TAGLINE, Wordmark } from '@/components/brand';

/** Routes where every number really is read from saved records or the committed RL bundle. */
export function showsRecordsFooter(pathname: string): boolean {
  return pathname === '/lab' || pathname.startsWith('/lab/') || pathname === '/projects' || pathname.startsWith('/projects/');
}

const DEMO_NOTE = 'Demo account. The organization, repositories, commits and illustrative results are sample data. The separately labelled recorded live run is saved evidence from an owned test fixture, not sample data or a run happening now.';
const RECORDS_NOTE = 'Every number here comes from saved records. Nothing is made up in your browser.';

/**
 * Brand footer on every page except the landing. The records-only promise holds for the
 * console and the Defense Lab only; marketing pages (pricing, sign-in) do not get it, because
 * it would be false there. The demo account (/demo, ADR 0013) says its data is sample data.
 * No links here: the header already carries navigation, and duplicates would only add noise.
 */
export function SiteFooter() {
  const pathname = usePathname();
  if (pathname === '/') return null;
  const note = pathname === '/demo' || pathname.startsWith('/demo/') ? DEMO_NOTE : showsRecordsFooter(pathname) ? RECORDS_NOTE : null;
  return (
    <footer className="night-footer mx-auto max-w-7xl px-4 pb-12 pt-10" data-testid="site-footer">
      <div className="flex flex-wrap items-center justify-between gap-x-8 gap-y-3">
        <Wordmark className="text-ink" />
        <p className="text-sm text-muted">{BRAND_TAGLINE}</p>
      </div>
      {note && <p className="label-mono mt-6 max-w-4xl leading-relaxed text-faint">{note}</p>}
    </footer>
  );
}
