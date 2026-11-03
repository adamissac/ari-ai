'use client';

import { useEffect } from 'react';

export function AnchorScroll() {
  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      if (
        event.defaultPrevented
        || event.button !== 0
        || event.metaKey
        || event.ctrlKey
        || event.shiftKey
        || event.altKey
        || window.matchMedia('(prefers-reduced-motion: reduce)').matches
      ) return;

      const target = event.target;
      if (!(target instanceof Element)) return;
      const anchor = target.closest<HTMLAnchorElement>('a[href*="#"]');
      if (!anchor || anchor.origin !== window.location.origin || anchor.pathname !== window.location.pathname || !anchor.hash) return;

      let id: string;
      try {
        id = decodeURIComponent(anchor.hash.slice(1));
      } catch {
        return;
      }
      const element = document.getElementById(id);
      if (!element) return;

      event.preventDefault();
      element.scrollIntoView({ behavior: 'smooth', block: 'start' });
      window.history.pushState(null, '', anchor.hash);
    };

    document.addEventListener('click', onClick);
    return () => document.removeEventListener('click', onClick);
  }, []);

  return null;
}
