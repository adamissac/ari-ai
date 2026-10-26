'use client';

import { useEffect, useRef, useState } from 'react';

type Position = { top: number; left: number; width: number; height: number; bubbleTop: number; bubbleLeft: number };

export function CoachMark({
  target,
  current,
  total,
  children,
  onNext,
  onBack,
  onSkip,
  nextDisabled = false,
  nextLabel = 'Next',
}: {
  target: string;
  current: number;
  total: number;
  children: string;
  onNext: () => void;
  onBack: () => void;
  onSkip?: () => void;
  nextDisabled?: boolean;
  nextLabel?: string;
}) {
  const bubbleRef = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState<Position | null>(null);

  useEffect(() => {
    const update = () => {
      const element = document.querySelector<HTMLElement>(`[data-coach="${target}"]`);
      if (!element) {
        setPosition({ top: 0, left: 0, width: 0, height: 0, bubbleTop: 24, bubbleLeft: 16 });
        return;
      }
      const rect = element.getBoundingClientRect();
      const bubbleWidth = Math.min(320, window.innerWidth - 32);
      const bubbleLeft = Math.max(16, Math.min(window.innerWidth - bubbleWidth - 16, rect.left + rect.width / 2 - bubbleWidth / 2));
      const bubbleHeight = 190;
      const above = rect.top - bubbleHeight - 16;
      const below = rect.bottom + 16;
      const bubbleTop = above >= 16 ? above : below + bubbleHeight < window.innerHeight ? below : Math.max(16, above);
      setPosition({
        top: rect.top,
        left: rect.left,
        width: rect.width,
        height: rect.height,
        bubbleTop,
        bubbleLeft,
      });
    };
    update();
    window.addEventListener('resize', update);
    window.addEventListener('scroll', update, true);
    return () => {
      window.removeEventListener('resize', update);
      window.removeEventListener('scroll', update, true);
    };
  }, [target, current]);

  useEffect(() => { bubbleRef.current?.focus(); }, [position]);

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
      {position.width > 0 && (
        <div
          aria-hidden="true"
          className="pointer-events-none fixed z-[100] rounded-xl border-2 border-brand motion-safe:transition-all motion-safe:duration-250"
          style={{
            top: position.top - 5,
            left: position.left - 5,
            width: position.width + 10,
            height: position.height + 10,
            boxShadow: '0 0 0 9999px rgb(9 7 6 / 66%), 0 0 24px rgb(255 126 47 / 32%)',
          }}
        />
      )}
      <div
        ref={bubbleRef}
        role="dialog"
        aria-label={`Setup guidance, question ${current} of ${total}`}
        tabIndex={-1}
        className="fixed z-[101] w-[min(20rem,calc(100vw-2rem))] rounded-xl border border-brand/40 bg-panel p-4 text-ink shadow-[0_12px_40px_rgb(0_0_0/45%)] outline-none motion-safe:animate-[fade-in_250ms_ease-out]"
        style={{ top: position.bubbleTop, left: position.bubbleLeft }}
      >
        <div aria-hidden="true" className="mb-2 font-mono text-xs text-brand motion-safe:animate-bounce">↓</div>
        <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted">Question {current} of {total}</p>
        <p className="mt-2 text-sm leading-5">{children}</p>
        <div className="mt-4 flex items-center gap-2">
          {onSkip && <button type="button" className="mr-auto text-xs text-muted hover:text-ink" onClick={onSkip}>Skip tour</button>}
          <button type="button" className="rounded-md border border-line px-3 py-1.5 text-xs hover:bg-panel-2" onClick={onBack}>Back</button>
          <button type="button" className="rounded-md bg-brand px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50" disabled={nextDisabled} onClick={onNext}>{nextLabel}</button>
        </div>
      </div>
    </>
  );
}
