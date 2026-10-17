'use client';

import { useEffect, useRef, useState, type ReactNode } from 'react';

/**
 * Full-screen interactive hero band. Pointer position and scroll progress are written as CSS
 * variables (--mx/--my on the band, --tx/--ty on each [data-spotlight] line, --scroll) once per
 * frame; all visuals live in globals.css (`.hero-stage`). While mounted it also drives the
 * floating site header through <html> data attributes: data-home-hero, data-hero-scrolled
 * (logo and tabs revealed) and data-hero-past (header switches to the light tone).
 * `play` starts the entrance (after the intro loader lifts). Without JS, or with reduced
 * motion, the band renders as a static dark hero with fully visible text.
 */
export function HeroStage({ children, className = '', labelledBy, play = true }: { children: ReactNode; className?: string; labelledBy: string; play?: boolean }) {
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const root = document.documentElement;
    root.dataset.homeHero = '';
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let frame = 0;
    let pointer: { x: number; y: number } | null = null;
    const paint = () => {
      frame = 0;
      const box = el.getBoundingClientRect();
      const height = Math.max(1, box.height);
      const y = window.scrollY;
      toggle(root, 'heroScrolled', y > 24);
      toggle(root, 'heroPast', y > height - 64);
      if (reduced) return;
      if (pointer) {
        el.style.setProperty('--mx', `${pointer.x - box.left}px`);
        el.style.setProperty('--my', `${pointer.y - box.top}px`);
        el.querySelectorAll<HTMLElement>('[data-spotlight]').forEach(line => {
          const r = line.getBoundingClientRect();
          line.style.setProperty('--tx', `${pointer!.x - r.left}px`);
          line.style.setProperty('--ty', `${pointer!.y - r.top}px`);
        });
      }
      el.style.setProperty('--scroll', Math.min(1, Math.max(0, y / height)).toFixed(3));
    };
    const schedule = () => { if (!frame) frame = requestAnimationFrame(paint); };
    const onMove = (e: PointerEvent) => { pointer = { x: e.clientX, y: e.clientY }; el.dataset.pointer = 'on'; schedule(); };
    const onLeave = () => { el.dataset.pointer = 'off'; };
    el.addEventListener('pointermove', onMove);
    el.addEventListener('pointerleave', onLeave);
    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', schedule);
    schedule();
    return () => {
      cancelAnimationFrame(frame);
      el.removeEventListener('pointermove', onMove);
      el.removeEventListener('pointerleave', onLeave);
      window.removeEventListener('scroll', schedule);
      window.removeEventListener('resize', schedule);
      delete root.dataset.homeHero;
      delete root.dataset.heroScrolled;
      delete root.dataset.heroPast;
    };
  }, []);

  useEffect(() => {
    const el = ref.current;
    if (el && play && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) el.dataset.fx = 'on';
  }, [play]);

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

function toggle(el: HTMLElement, key: string, on: boolean) {
  if (on) el.dataset[key] = '';
  else delete el.dataset[key];
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
