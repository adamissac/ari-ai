'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { RollText } from '@/components/ui';
import { api } from '@/lib/api';
import { DEMO_USER } from '@/lib/demo/data';
import { DEMO_ONLY } from '@/lib/deployment';

const DEMO_HOME_PATH = '/demo/lumen-pay';

/**
 * Top-right account entry in the site header. Signed out (or backend unreachable): "Sign in",
 * which opens the console's sign-in screen (or /access on the demo-only deployment). Signed in:
 * the user's GitHub login, linking to their projects. Re-checked on every route change.
 */
export function AccountLink() {
  const pathname = usePathname();
  const [login, setLogin] = useState<string | null>(null);

  const [href, setHref] = useState('/projects');

  useEffect(() => {
    const c = new AbortController();
    const demoAccount = () =>
      fetch('/api/demo-session', { signal: c.signal, cache: 'no-store' })
        .then(r => r.json() as Promise<{ signedIn?: boolean }>)
        .then(body => {
          setLogin(body.signedIn ? DEMO_USER.login : null);
          setHref(DEMO_HOME_PATH);
        });
    const backend = DEMO_ONLY ? Promise.reject(new Error('no backend')) : api().session({ signal: c.signal });
    backend.then(
      me => { setLogin(me.user.github_login); setHref('/projects'); },
      () => { if (!c.signal.aborted) demoAccount().catch(() => { if (!c.signal.aborted) setLogin(null); }); },
    );
    return () => c.abort();
  }, [pathname]);

  if (login) {
    return (
      <Link
        href={href}
        className="group hdr-account label-mono inline-flex h-8 items-center gap-2 rounded-md px-2 sm:px-3"
        title={`Signed in as ${login}`}
        aria-label={`Signed in as ${login}`}
        data-testid="header-account"
      >
        <span aria-hidden="true" className="hdr-avatar">{login.slice(0, 1).toUpperCase()}</span>
        {/* Phone: avatar only — full login chip overflows 375px with the rest of the nav. */}
        <span className="hidden max-w-[8rem] truncate normal-case sm:inline">{login}</span>
        <span className="sr-only sm:hidden">{login}</span>
      </Link>
    );
  }
  return (
    <Link
      href={DEMO_ONLY ? '/access' : '/projects'}
      className="group hdr-signin label-mono inline-flex h-8 items-center rounded-md px-2 sm:px-3"
      data-testid="header-signin"
    >
      <RollText>Sign in</RollText>
    </Link>
  );
}
