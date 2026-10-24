'use client';

import { useEffect, useRef, type CSSProperties, type ReactNode } from 'react';

/**
 * Per-letter blur-in text (the signature landing reveal). Each letter is a .lt span
 * carrying its index in --l; the closest [data-lt] scope decides playback:
 *   "idle" (default): letters render normally — SSR, no-JS and reduced motion stay readable.
 *   "off": letters hidden (set by JS only, for content below the fold).
 *   "on": letters animate in, staggered by --l (styles in globals.css).
 * Screen readers get the plain sr-only text; the split copy is aria-hidden.
 */
export function Letters({ text, from = 0 }: { text: string; from?: number }) {
  let n = from;
  const parts: ReactNode[] = [];
  text.split(' ').forEach((word, wi) => {
    if (wi > 0) parts.push(' ');
    parts.push(
      <span key={wi} className="lt-word">
        {Array.from(word).map((ch, ci) => (
          <span key={ci} className="lt" style={{ '--l': n++ } as CSSProperties}>{ch}</span>
        ))}
      </span>,
    );
  });
  return (
    <>
      <span className="sr-only">{text}</span>
      <span aria-hidden="true" className="lts">{parts}</span>
    </>
  );
}

/**
 * Scope that plays its Letters once when first scrolled into view. Elements already on
 * screen play immediately; elements below the fold are hidden until the reveal. Under
 * reduced motion or without JS the attribute stays "idle" and text is simply shown.
 */
export function LetterScope({ children, className = '', tag: Tag = 'span' }: { children: ReactNode; className?: string; tag?: 'span' | 'div' | 'p' | 'h2' | 'h3' }) {
  const ref = useRef<HTMLElement | null>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === 'undefined') return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    if (el.getBoundingClientRect().top < window.innerHeight * 0.75) { el.dataset.lt = 'on'; return; }
    el.dataset.lt = 'off';
    const io = new IntersectionObserver(([entry]) => {
      if (!entry?.isIntersecting) return;
      el.dataset.lt = 'on';
      io.disconnect();
    }, { rootMargin: '0px 0px -10% 0px' });
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return <Tag ref={ref as never} data-lt="idle" className={`lt-scope ${className}`}>{children}</Tag>;
}
