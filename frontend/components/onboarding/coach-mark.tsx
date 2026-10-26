'use client';

import { useEffect, useRef, useState } from 'react';

type Mode = 'setup' | 'tour';
type Position = {
  top: number;
  left: number;
  width: number;
  height: number;
  bubbleTop: number;
  bubbleLeft: number;
  pointerLeft: number;
  pointerLength: number;
  pointer: 'left' | 'down' | 'up';
};

export function CoachMark({
  mode,
  target,
  current,
  total,
  children,
  onNext,
  onSkip,
}: {
  mode: Mode;
  target: string;
  current: number;
  total: number;
  children: string;
  onNext?: () => void;
  onSkip?: () => void;
}) {
  const bubbleRef = useRef<HTMLDivElement>(null);
  const focused = useRef(false);
  const [position, setPosition] = useState<Position | null>(null);
  const [bubbleVisible, setBubbleVisible] = useState(true);

  useEffect(() => {
    let didRevealTarget = false;
    const update = () => {
      const element = document.querySelector<HTMLElement>(`[data-coach="${target}"]`);
      if (!element) {
        setPosition(null);
        return false;
      }
      if (!didRevealTarget) {
        element.scrollIntoView?.({ block: 'nearest', inline: 'nearest' });
        const siteNavBottom = document.querySelector('.site-header')?.getBoundingClientRect().bottom ?? 0;
        const targetTop = element.getBoundingClientRect().top;
        if (siteNavBottom > 0 && targetTop < siteNavBottom + 12) window.scrollBy?.(0, targetTop - siteNavBottom - 12);
        didRevealTarget = true;
      }
      const rect = element.getBoundingClientRect();
      const bubbleWidth = Math.min(288, window.innerWidth - 32);
      const bubbleHeight = mode === 'tour' ? 152 : 100;
      const pointer = mode === 'tour' ? 'up' : window.innerWidth >= 1024 ? 'left' : 'down';
      const tabBandBottom = document.querySelector('.project-tabbar')?.getBoundingClientRect().bottom ?? rect.bottom;
      const tourBubbleTop = Math.min(tabBandBottom + 14, window.innerHeight - bubbleHeight - 16);
      const bubbleLeft = pointer === 'left'
        ? rect.right + 16
        : Math.max(16, Math.min(window.innerWidth - bubbleWidth - 16, rect.left + rect.width / 2 - bubbleWidth / 2));
      const bubbleTop = mode === 'tour'
        ? tourBubbleTop
        : pointer === 'left'
          ? Math.max(16, Math.min(window.innerHeight - bubbleHeight - 16, rect.top + 8))
          : Math.max(16, rect.top - bubbleHeight - 12);
      const pointerLeft = Math.max(16, Math.min(bubbleWidth - 16, rect.left + rect.width / 2 - bubbleLeft));
      setPosition({
        top: rect.top,
        left: rect.left,
        width: rect.width,
        height: rect.height,
        bubbleTop,
        bubbleLeft,
        pointerLeft,
        pointerLength: pointer === 'up' ? Math.max(27, bubbleTop - rect.bottom) : 27,
        pointer,
      });
      return true;
    };
    const foundTarget = update();
    const observer = foundTarget ? null : new MutationObserver(() => {
      if (update()) observer?.disconnect();
    });
    observer?.observe(document.body, { childList: true, subtree: true });
    window.addEventListener('resize', update);
    window.addEventListener('scroll', update, true);
    return () => {
      observer?.disconnect();
      window.removeEventListener('resize', update);
      window.removeEventListener('scroll', update, true);
    };
  }, [mode, target, current]);

  useEffect(() => {
    if (position && bubbleVisible && !focused.current) {
      bubbleRef.current?.focus();
      focused.current = true;
    }
  }, [position, bubbleVisible]);

  useEffect(() => {
    const preventEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
      }
    };
    window.addEventListener('keydown', preventEscape, true);
    return () => window.removeEventListener('keydown', preventEscape, true);
  }, []);

  if (!position) return null;
  return (
    <>
      <div
        aria-hidden="true"
        data-testid="coach-spotlight"
        className="pointer-events-none fixed z-[100] rounded-xl border-2 border-brand"
        style={{
          top: position.top - 5,
          left: position.left - 5,
          width: position.width + 10,
          height: position.height + 10,
          boxShadow: '0 0 0 9999px rgb(9 7 6 / 66%), 0 0 24px rgb(255 126 47 / 32%)',
        }}
      />
      {bubbleVisible && (
        <div
          ref={bubbleRef}
          role="dialog"
          aria-label={mode === 'tour' ? `Tip ${current} of ${total}` : 'Setup tip'}
          tabIndex={-1}
          className={`fixed z-[101] w-[min(18rem,calc(100vw-2rem))] rounded-xl border border-brand/40 bg-panel text-ink shadow-[0_12px_40px_rgb(0_0_0/45%)] outline-none motion-safe:animate-[fade-in_250ms_ease-out] ${mode === 'tour' ? 'p-4' : 'p-3'}`}
          style={{ top: position.bubbleTop, left: position.bubbleLeft }}
        >
          <span
            aria-hidden="true"
            className={`coach-pointer coach-pointer--${position.pointer}`}
            style={{
              left: position.pointer === 'left' ? undefined : position.pointerLeft,
              ...(position.pointer === 'up' ? { top: -position.pointerLength, height: position.pointerLength } : {}),
            }}
          />
          {mode === 'tour' && <p className="font-mono text-[10px] tracking-[0.12em] text-muted">Tip {current} of {total}</p>}
          <p className={`${mode === 'tour' ? 'mt-2 text-sm leading-5' : 'text-xs leading-4'}`}>{children}</p>
          <div className={`${mode === 'tour' ? 'mt-4' : 'mt-3'} flex items-center gap-2`}>
            {mode === 'setup'
              ? <button type="button" className="ml-auto min-h-11 rounded-md bg-brand px-4 py-2 text-xs font-semibold text-white" onClick={() => setBubbleVisible(false)}>Got it</button>
              : <>
                <button type="button" className="mr-auto min-h-11 text-xs text-muted hover:text-ink" onClick={onSkip}>Skip tour</button>
                <button type="button" className="min-h-11 rounded-md bg-brand px-4 py-2 text-xs font-semibold text-white" onClick={onNext}>Next</button>
              </>}
          </div>
        </div>
      )}
    </>
  );
}
