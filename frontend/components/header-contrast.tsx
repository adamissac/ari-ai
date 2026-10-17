'use client';

import { usePathname } from 'next/navigation';
import { useEffect } from 'react';

/** Resolve the nearest painted surface, including light cards inside dark sections. */
export function isDarkSurface(element: Element | null): boolean {
  for (let surface = element; surface; surface = surface.parentElement) {
    const rgb = getComputedStyle(surface).backgroundColor.match(/^rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)$/);
    if (!rgb || Number(rgb[4] ?? 1) < 1) continue;
    const [r, g, b] = rgb.slice(1, 4).map(channel => {
      const c = Number(channel) / 255;
      return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * r! + 0.7152 * g! + 0.0722 * b! < 0.18;
  }
  return false;
}

/** Adapt transparent controls individually when a section boundary crosses the header.
 * Read once per animation frame; write attributes only when the contrast changes. */
export function HeaderContrast() {
  const pathname = usePathname();
  useEffect(() => {
    const header = document.querySelector('.site-header');
    if (!header) return;
    let frame = 0;
    const paint = () => {
      frame = 0;
      // While the pinned home hero is still under the header, keep white ink even if
      // hit-testing misses the dark band (gradients / stacked layers can look "light").
      const overHomeHero =
        document.documentElement.hasAttribute('data-home-hero')
        && !document.documentElement.hasAttribute('data-hero-past');
      const tones = [...header.querySelectorAll<HTMLElement>('a:not(.hdr-cta), .nav-menu-toggle')].map(link => {
        const box = link.getBoundingClientRect();
        const underneath = document.elementsFromPoint(box.x + box.width / 2, box.y + box.height / 2)
          .find(element => !header.contains(element)) ?? null;
        const tone = overHomeHero || isDarkSurface(underneath) ? 'dark' : 'light';
        return { link, tone };
      });
      for (const { link, tone } of tones) {
        if (link.dataset.navTone !== tone) link.dataset.navTone = tone;
      }
    };
    const schedule = () => { if (!frame) frame = requestAnimationFrame(paint); };
    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', schedule);
    const observer = new MutationObserver(schedule);
    observer.observe(header, { childList: true, subtree: true });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-home-hero', 'data-hero-past'] });
    schedule();
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('scroll', schedule);
      window.removeEventListener('resize', schedule);
      observer.disconnect();
    };
  }, [pathname]);
  return null;
}
