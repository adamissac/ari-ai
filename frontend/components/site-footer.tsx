'use client';

import { usePathname } from 'next/navigation';

/**
 * The records-only promise holds for the console and the Defense Lab. The landing
 * page (/) is made of labelled illustrations, so the line is not shown there. The simulated
 * demo (/demo, ADR 0013) says the opposite, plainly.
 */
export function SiteFooter() {
  const pathname = usePathname();
  if (pathname === '/') return null;
  if (pathname.startsWith('/demo')) {
    return (
      <footer className="label-mono mx-auto max-w-7xl border-t border-line px-4 py-6 text-faint" data-testid="site-footer">
        Simulated demo. Accounts, repositories, commits and agent runs on these pages are illustrative.
      </footer>
    );
  }
  return (
    <footer className="label-mono mx-auto max-w-7xl border-t border-line px-4 py-6 text-faint" data-testid="site-footer">
      Every number here comes from saved records. Nothing is made up in your browser.
    </footer>
  );
}
