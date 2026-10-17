'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { RollText } from '@/components/ui';
import { api } from '@/lib/api';
import { DEMO_ONLY } from '@/lib/deployment';

/**
 * Top-right account entry in the site header. Signed out (or backend unreachable): "Sign in",
 * which opens the console's sign-in screen (or /demo on the demo-only deployment). Signed in:
 * the user's GitHub login, linking to their projects. Re-checked on every route change.
 */
export function AccountLink() {
  const pathname = usePathname();
  const [login, setLogin] = useState<string | null>(null);

  useEffect(() => {
    if (DEMO_ONLY) return;
    const c = new AbortController();
    api().session({ signal: c.signal }).then(
      me => setLogin(me.user.github_login),
      () => { if (!c.signal.aborted) setLogin(null); },
    );
    return () => c.abort();
  }, [pathname]);

  if (login) {
    return (
      <Link
        href="/projects"
        className="group hdr-account label-mono inline-flex h-8 items-center gap-2 rounded-md px-2 sm:px-3"
        title={`Signed in as ${login}`}
        aria-label={`Signed in as ${login}`}
        data-testid="header-account"
      >
        <span aria-hidden="true" className="hdr-avatar">{login.slice(0, 1).toUpperCase()}</span>
        {/* Phone widths cannot fit Projects + Lab + Demo + Pricing + a full login chip. */}
        <span className="hidden max-w-[8rem] truncate normal-case sm:inline">{login}</span>
      </Link>
    );
  }
  return (
    <Link
      href={DEMO_ONLY ? '/demo' : '/projects'}
      className="group hdr-signin label-mono inline-flex h-8 items-center rounded-md px-2 sm:px-3"
      data-testid="header-signin"
    >
      <RollText>Sign in</RollText>
    </Link>
  );
}
