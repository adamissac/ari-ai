'use client';

import { useEffect, useRef, useState, type ReactNode } from 'react';

/**
 * Interactive hero band. Pointer position and scroll progress are written as CSS variables
 * (--mx/--my on the band, --tx/--ty on each [data-spotlight] line, --scroll) once per frame;
 * all visuals live in globals.css (`.hero-stage`). Without JS, or with reduced motion, the
 * band renders as a static dark hero with fully visible text.
 */
export function HeroStage({ children, className = '', labelledBy }: { children: ReactNode; className?: string; labelledBy: string }) {
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    let frame = 0;
    let pointer: { x: number; y: number } | null = null;
    const paint = () => {
      frame = 0;
      const box = el.getBoundingClientRect();
      if (pointer) {
        el.style.setProperty('--mx', `${pointer.x - box.left}px`);
        el.style.setProperty('--my', `${pointer.y - box.top}px`);
        el.querySelectorAll<HTMLElement>('[data-spotlight]').forEach(line => {
          const r = line.getBoundingClientRect();
          line.style.setProperty('--tx', `${pointer!.x - r.left}px`);
          line.style.setProperty('--ty', `${pointer!.y - r.top}px`);
        });
      }
      el.style.setProperty('--scroll', Math.min(1, Math.max(0, -box.top / Math.max(1, box.height))).toFixed(3));
    };
    const schedule = () => { if (!frame) frame = requestAnimationFrame(paint); };
    const onMove = (e: PointerEvent) => { pointer = { x: e.clientX, y: e.clientY }; el.dataset.pointer = 'on'; schedule(); };
    const onLeave = () => { el.dataset.pointer = 'off'; };
    el.addEventListener('pointermove', onMove);
    el.addEventListener('pointerleave', onLeave);
    window.addEventListener('scroll', schedule, { passive: true });
    el.dataset.fx = 'on';
    schedule();
    return () => {
      cancelAnimationFrame(frame);
      el.removeEventListener('pointermove', onMove);
      el.removeEventListener('pointerleave', onLeave);
      window.removeEventListener('scroll', schedule);
    };
  }, []);
  return (
    <section ref={ref} className={`hero-ink hero-stage ${className}`} aria-labelledby={labelledBy}>
      <div aria-hidden="true" className="hero-orbs">
        <span className="hero-orb hero-orb-a" />
        <span className="hero-orb hero-orb-b" />
        <span className="hero-orb hero-orb-c" />
        <span className="hero-glow" />
      </div>
      <div className="hero-content">{children}</div>
    </section>
  );
}

/** Highlights each loop step in turn, like a pipeline running. Static under reduced motion. */
export function useLoopCursor(length: number, ms = 1400): number {
  const [active, setActive] = useState(-1);
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    let i = -1;
    const id = window.setInterval(() => { i = (i + 1) % length; setActive(i); }, ms);
    return () => window.clearInterval(id);
  }, [length, ms]);
  return active;
}
