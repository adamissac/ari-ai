'use client';

import { useEffect, useState } from 'react';
import { BRAND_NAME } from '@/components/brand';

/** Session key: the intro plays once per sign-in (cleared on sign-out, see session.tsx). */
export const INTRO_KEY = 'ari-intro-played';

const DURATION_MS = 1800;
const LIFT_MS = 800;

function shouldPlay(): boolean {
  if (typeof window === 'undefined') return false;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return false;
  if (navigator.webdriver) return false; // automated browsers (e2e) skip straight to the page
  try { return window.sessionStorage.getItem(INTRO_KEY) === null; } catch { return false; }
}

/**
 * Full-screen intro shown on the home hero right after sign-in: the mark draws itself while a
 * percentage counts up, then the curtain lifts and `onReveal` starts the hero entrance. It never
 * intercepts input (pointer-events: none), and is skipped under reduced motion or automation.
 */
export function IntroLoader({ onReveal }: { onReveal: () => void }) {
  const [play] = useState(shouldPlay);
  const [pct, setPct] = useState(0);
  const [phase, setPhase] = useState<'count' | 'lift' | 'gone'>(play ? 'count' : 'gone');

  useEffect(() => {
    if (!play) { onReveal(); return; }
    const root = document.documentElement;
    root.dataset.intro = 'playing';
    let frame = 0;
    let liftTimer = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / DURATION_MS);
      setPct(Math.round((1 - Math.pow(1 - t, 3)) * 100));
      if (t < 1) { frame = requestAnimationFrame(tick); return; }
      try { window.sessionStorage.setItem(INTRO_KEY, '1'); } catch { /* storage unavailable: replay is harmless */ }
      setPhase('lift');
      delete root.dataset.intro;
      onReveal();
      liftTimer = window.setTimeout(() => setPhase('gone'), LIFT_MS);
    };
    frame = requestAnimationFrame(tick);
    return () => { cancelAnimationFrame(frame); window.clearTimeout(liftTimer); delete root.dataset.intro; };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- runs once per mount by design
  }, []);

  if (phase === 'gone') return null;
  return (
    <div aria-hidden="true" className="intro" data-phase={phase}>
      <svg className="intro-mark" viewBox="0 0 60 60" role="presentation">
        <rect x="2" y="2" width="56" height="56" rx="10" pathLength={1} />
        <path d="M19 45 L30 15 L41 45 M23.5 34 H36.5" pathLength={1} />
      </svg>
      <div className="intro-progress">
        <span className="intro-pct">{pct}%</span>
        <span className="intro-line" style={{ transform: `scaleX(${pct / 100})` }} />
      </div>
      <span className="sr-only">{BRAND_NAME}</span>
    </div>
  );
}
