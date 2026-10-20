'use client';

import { usePathname } from 'next/navigation';
import { useEffect } from 'react';

/**
 * Momentum ("smooth") scrolling for mouse wheels and trackpads, like kairo.security's Lenis,
 * without a dependency. Wheel input moves a target scroll position and the page eases toward
 * it each frame. Native scrolling is kept for touch, keyboard, the scrollbar, pinch-zoom,
 * horizontal gestures, nested scroll areas, and anyone who prefers reduced motion.
 */
const EASE = 0.11; // share of the remaining distance covered per 60 Hz frame (lower = longer glide)
const FRAME = 1000 / 60;
const LINE = 16;

function scrollableParent(el: Element | null, dy: number): Element | null {
  for (let n = el; n && n !== document.body && n !== document.documentElement; n = n.parentElement) {
    const style = getComputedStyle(n);
    if (!/(auto|scroll)/.test(style.overflowY) || n.scrollHeight <= n.clientHeight) continue;
    const atTop = n.scrollTop <= 0;
    const atBottom = n.scrollTop + n.clientHeight >= n.scrollHeight - 1;
    if ((dy < 0 && !atTop) || (dy > 0 && !atBottom)) return n;
  }
  return null;
}

export function SmoothScroll() {
  const pathname = usePathname();
  useEffect(() => {
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
    const coarse = window.matchMedia('(pointer: coarse)');
    let target = window.scrollY;
    let current = window.scrollY;
    let frame = 0;
    let animating = false;
    // Consume only the arriving wheel gesture, never force playback or lock navigation.
    let videoStopUsed = pathname !== '/' || Boolean(location.hash);
    let holdingVideo = false;
    let videoArrival = 0;
    let lastVideoWheel = 0;

    const max = () => document.documentElement.scrollHeight - window.innerHeight;
    const stop = () => { cancelAnimationFrame(frame); animating = false; };
    let last = 0;
    const tick = (now: number) => {
      // Frame-rate independent: the same glide on 60 Hz and 120 Hz screens.
      const dt = last ? Math.max(1, Math.min(64, now - last)) : FRAME;
      last = now;
      current += (target - current) * (1 - Math.pow(1 - (pathname === '/' ? 0.085 : EASE), dt / FRAME));
      if (Math.abs(target - current) < 0.5) current = target;
      animating = current !== target;
      window.scrollTo(0, current);
      if (animating) frame = requestAnimationFrame(tick);
    };
    const start = () => { if (!animating) { animating = true; last = 0; frame = requestAnimationFrame(tick); } };

    const onWheel = (e: WheelEvent) => {
      if (reduced.matches || coarse.matches || e.ctrlKey || e.defaultPrevented) return;
      if (Math.abs(e.deltaX) > Math.abs(e.deltaY)) return;
      const dy = e.deltaMode === 1 ? e.deltaY * LINE : e.deltaMode === 2 ? e.deltaY * window.innerHeight : e.deltaY;
      if (e.target instanceof Element && scrollableParent(e.target, dy)) return;
      e.preventDefault();
      if (!animating) { current = window.scrollY; target = current; }
      const now = performance.now();
      if (holdingVideo) {
        const newGesture = now - lastVideoWheel > 180;
        const timeout = now - videoArrival > 1200;
        lastVideoWheel = now;
        if (dy > 0 && !newGesture && !timeout) return;
        holdingVideo = false;
      }
      // Bound both a single large flick and queued momentum on the landing story.
      // Continued intentional scrolling still moves freely; touch and reduced motion stay native.
      const reading = pathname === '/' && Boolean(document.querySelector('[data-reading-chapter]'));
      const delta = reading ? Math.sign(dy) * Math.min(Math.abs(dy), innerHeight * 0.65) : dy;
      const proposed = target + delta;
      const nextTarget = reading ? Math.max(current - innerHeight * 0.85, Math.min(current + innerHeight * 0.85, proposed)) : proposed;
      let next = Math.max(0, Math.min(max(), nextTarget));
      if (!videoStopUsed && dy > 0) {
        const chapter = document.getElementById('explainer');
        if (chapter) {
          const rect = chapter.getBoundingClientRect();
          // Stop where the sticky video has expanded to full size (growth ends at 45%).
          const landing = Math.min(max(), rect.top + window.scrollY + Math.max(0, rect.height - innerHeight) * 0.5);
          if (current >= landing) videoStopUsed = true;
          else if (next >= landing) {
            next = landing;
            videoStopUsed = true;
            holdingVideo = true;
            videoArrival = lastVideoWheel = now;
          }
        }
      }
      target = next;
      start();
    };
    // Keyboard, scrollbar and programmatic jumps: follow the page and drop any momentum.
    const onScroll = () => { if (!animating) { current = window.scrollY; target = current; } };
    const onKey = () => { holdingVideo = false; stop(); };
    const onPointer = (e: PointerEvent) => { if (e.pointerType !== 'mouse' || e.button !== 1) stop(); };
    // In-page anchors glide to their target too.
    const onClick = (e: MouseEvent) => {
      if (reduced.matches || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey) return;
      const a = (e.target as Element).closest?.('a[href*="#"]') as HTMLAnchorElement | null;
      if (!a || a.origin !== location.origin || a.pathname !== location.pathname || !a.hash) return;
      const el = document.getElementById(decodeURIComponent(a.hash.slice(1)));
      if (!el) return;
      e.preventDefault();
      const marginTop = parseFloat(getComputedStyle(el).scrollMarginTop) || 0;
      current = window.scrollY;
      target = Math.max(0, Math.min(max(), el.getBoundingClientRect().top + window.scrollY - marginTop));
      // Explicit anchor navigation is intentional, so never pull it back to the video.
      holdingVideo = false;
      videoStopUsed = true;
      history.pushState(null, '', a.hash);
      start();
    };

    window.addEventListener('wheel', onWheel, { passive: false });
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('keydown', onKey);
    window.addEventListener('pointerdown', onPointer);
    document.addEventListener('click', onClick);
    document.documentElement.dataset.smoothScroll = '';
    return () => {
      stop();
      window.removeEventListener('wheel', onWheel);
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('pointerdown', onPointer);
      document.removeEventListener('click', onClick);
      delete document.documentElement.dataset.smoothScroll;
    };
  }, [pathname]); // re-arm per route so momentum never carries over to the next page
  return null;
}
