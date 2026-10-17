'use client';

import { usePathname } from 'next/navigation';
import { useCallback, useRef, useState, useSyncExternalStore, type KeyboardEvent } from 'react';
import { AccountLink } from '@/components/account-link';
import { NavLink } from '@/components/nav-link';

const hasScrolled = () => window.scrollY >= 100;
const serverTop = () => false;
const noSubscription = () => () => {};

/** Keep the account slot fixed while the homepage's secondary links fade in/out. */
export function SiteNavigation() {
  const pathname = usePathname();
  return (
    <nav aria-label="Primary" className="site-nav">
      <NavigationLinks key={pathname} home={pathname === '/'} />
      <AccountLink />
    </nav>
  );
}

function NavigationLinks({ home }: { home: boolean }) {
  const menu = useRef<HTMLButtonElement>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const subscribe = useCallback((notify: () => void) => {
    let previous = hasScrolled();
    const onScroll = () => {
      const next = hasScrolled();
      if (next === previous) return;
      previous = next;
      if (next) setMenuOpen(false);
      notify();
    };
    const onResize = () => setMenuOpen(false);
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onResize);
    return () => {
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onResize);
    };
  }, []);
  const scrolled = useSyncExternalStore(home ? subscribe : noSubscription, hasScrolled, serverTop);
  const visible = !home || scrolled || menuOpen;
  const needsMenu = home && !scrolled;
  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key !== 'Escape' || !menuOpen) return;
    setMenuOpen(false);
    menu.current?.focus();
  };

  return (
    <>
      <button ref={menu} type="button" className="nav-menu-toggle label-mono rounded-md px-3" aria-controls="primary-links" aria-expanded={menuOpen} disabled={!needsMenu} data-needed={needsMenu} onKeyDown={onKeyDown} onClick={() => setMenuOpen(open => !open)}>
        Menu
      </button>
      <div id="primary-links" className="nav-secondary" data-visible={visible} aria-hidden={!visible} inert={!visible} onKeyDown={onKeyDown} onClick={() => setMenuOpen(false)}>
        <NavLink href="/projects">Projects</NavLink>
        <NavLink href="/lab">Defense Lab</NavLink>
        <NavLink href="/demo">Demo</NavLink>
        <NavLink href="/pricing" className="hdr-cta">Pricing</NavLink>
      </div>
    </>
  );
}
