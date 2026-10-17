'use client';

import { usePathname } from 'next/navigation';

/** Routes where every number really is read from saved records or the committed RL bundle. */
export function showsRecordsFooter(pathname: string): boolean {
  return pathname === '/lab' || pathname.startsWith('/lab/') || pathname === '/projects' || pathname.startsWith('/projects/');
}

/**
 * The records-only promise holds for the console and the Defense Lab only. Marketing
 * pages (landing illustrations, pricing) do not get it, because it would be false there.
 * The simulated demo (/demo, ADR 0013) says the opposite, plainly.
 */
export function SiteFooter() {
  const pathname = usePathname();
  if (pathname === '/demo' || pathname.startsWith('/demo/')) {
    return (
      <footer className="label-mono mx-auto max-w-7xl border-t border-line px-4 py-6 text-faint" data-testid="site-footer">
        Simulated demo. Accounts, repositories, commits and agent runs on these pages are illustrative.
      </footer>
    );
  }
  if (!showsRecordsFooter(pathname)) return null;
  return (
    <footer className="label-mono mx-auto max-w-7xl border-t border-line px-4 py-6 text-faint" data-testid="site-footer">
      Every number here comes from saved records. Nothing is made up in your browser.
    </footer>
  );
}
