'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { RollText } from '@/components/ui';

/** A header section is current on its own page and every page beneath it. */
export function isCurrentSection(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function NavLink({ href, children, className = '' }: { href: string; children: string; className?: string }) {
  const pathname = usePathname();
  const current = isCurrentSection(pathname, href) || (href === '/projects' && isCurrentSection(pathname, '/connect'));
  return (
    <Link
      href={href}
      aria-current={current ? 'page' : undefined}
      className={`group label-mono inline-flex h-8 items-center rounded-md bg-brand/[0.06] px-3 text-ink transition-colors duration-[250ms] hover:bg-brand hover:text-on-brand ${className}`}
    >
      <RollText>{children}</RollText>
    </Link>
  );
}
