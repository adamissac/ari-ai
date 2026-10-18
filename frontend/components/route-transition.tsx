'use client';

import { usePathname } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';
import { BRAND_NAME, LogoMark } from '@/components/brand';

/** The part of the site a path belongs to. Moving between parts plays the transition. */
export function sectionOf(pathname: string): string {
  const first = pathname.split('/')[1] ?? '';
  if (first === '') return 'home';
  if (first === 'projects' || first === 'connect') return 'console';
  return first;
}

/**
 * Whether going from one path to another plays the full-screen transition: only between
 * different parts of the site, never into the landing (it has its own intro) and never for
 * API routes (full-page navigations such as GitHub sign-in).
 */
export function playsTransition(from: string, to: string): boolean {
  if (to.startsWith('/api/')) return false;
  const target = sectionOf(to);
  return target !== 'home' && target !== sectionOf(from);
}

function allowed(): boolean {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return false;
  return !navigator.webdriver; // automated browsers (e2e) skip it, like the intro loader
}

const MIN_MS = 650; // the veil stays at least this long so it never flickers
const FINISH_MS = 220;
const LIFT_MS = 750;
const GIVE_UP_MS = 8000; // if the next page never arrives, lift anyway

type Phase = 'idle' | 'cover' | 'lift';

/**
 * Full-screen page change, in the look of the landing's first-load intro: the mark, a running
 * percentage and a load bar on warm ink. It covers the page on a click into another part of the
 * site, runs while the next page loads, completes when it has rendered, then lifts away. It never
 * intercepts input (pointer-events: none) and is skipped under reduced motion or automation.
 */
export function RouteTransition() {
  const pathname = usePathname();
  const [phase, setPhase] = useState<Phase>('idle');
  const [pct, setPct] = useState(0);
  const run = useRef<{ start: number; arrived: number | null; frame: number; timers: number[] } | null>(null);

  const stop = useCallback(() => {
    const r = run.current;
    if (!r) return;
    cancelAnimationFrame(r.frame);
    r.timers.forEach(id => window.clearTimeout(id));
    run.current = null;
  }, []);

  const lift = useCallback(() => {
    const r = run.current;
    if (!r) return;
    cancelAnimationFrame(r.frame);
    setPct(100);
    setPhase('lift');
    r.timers.push(window.setTimeout(() => { stop(); setPhase('idle'); setPct(0); }, LIFT_MS));
  }, [stop]);

  const start = useCallback(() => {
    stop();
    const r = { start: performance.now(), arrived: null as number | null, frame: 0, timers: [] as number[] };
    run.current = r;
    setPct(0);
    setPhase('cover');
    const tick = (now: number) => {
      const elapsed = now - r.start;
      if (r.arrived === null) {
        // Waiting for the next page: ease toward 90%.
        setPct(Math.round(90 * (1 - Math.exp(-elapsed / 420))));
      } else {
        const sinceArrival = now - Math.max(r.arrived, r.start + MIN_MS - FINISH_MS);
        if (sinceArrival >= FINISH_MS) { lift(); return; }
        if (sinceArrival > 0) setPct(p => Math.max(p, Math.round(90 + (sinceArrival / FINISH_MS) * 10)));
      }
      r.frame = requestAnimationFrame(tick);
    };
    r.frame = requestAnimationFrame(tick);
    r.timers.push(window.setTimeout(() => { if (run.current === r && r.arrived === null) r.arrived = performance.now(); }, GIVE_UP_MS));
  }, [lift, stop]);

  // A click on a link into another part of the site starts the veil before Next navigates.
  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const a = (e.target as Element | null)?.closest?.('a[href]') as HTMLAnchorElement | null;
      if (!a || (a.target && a.target !== '_self') || a.hasAttribute('download') || a.origin !== location.origin) return;
      if (!playsTransition(location.pathname, a.pathname) || !allowed()) return;
      start();
    };
    let last = location.pathname;
    const onPop = () => {
      const next = location.pathname;
      if (playsTransition(last, next) && allowed()) start();
      last = next;
    };
    document.addEventListener('click', onClick, true);
    window.addEventListener('popstate', onPop);
    return () => {
      document.removeEventListener('click', onClick, true);
      window.removeEventListener('popstate', onPop);
    };
  }, [start]);

  // The new page has rendered: finish the bar, then lift.
  useEffect(() => {
    const r = run.current;
    if (r && r.arrived === null) r.arrived = performance.now();
  }, [pathname]);

  useEffect(() => stop, [stop]);

  if (phase === 'idle') return null;
  return (
    <div aria-hidden="true" className="route-veil" data-phase={phase}>
      <LogoMark size={96} decorative className="route-veil-mark" />
      <div className="route-veil-progress">
        <span className="route-veil-pct">{pct}%</span>
        <span className="route-veil-line" style={{ transform: `scaleX(${pct / 100})` }} />
      </div>
      <span className="sr-only">{BRAND_NAME}</span>
    </div>
  );
}
