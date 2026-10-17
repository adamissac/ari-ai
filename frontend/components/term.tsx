'use client';

import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { GLOSSARY, type GlossaryTerm } from '@/lib/glossary';

/** Align the popover to the trigger's right edge when the trigger sits in the right half of the viewport. */
export function popoverAlign(triggerLeft: number, triggerWidth: number, viewportWidth: number): 'left' | 'right' {
  return triggerLeft + triggerWidth / 2 > viewportWidth / 2 ? 'right' : 'left';
}

/** A jargon word with an inline definition that opens on click/Enter and closes on Escape or blur. */
export function Term({ t, children }: { t: GlossaryTerm; children?: ReactNode }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const ref = useRef<HTMLSpanElement>(null);
  const btn = useRef<HTMLButtonElement>(null);
  const [align, setAlign] = useState<'left' | 'right'>('left');
  const toggle = () => {
    if (!open) {
      const r = btn.current?.getBoundingClientRect();
      if (r) setAlign(popoverAlign(r.left, r.width, window.innerWidth));
    }
    setOpen(o => !o);
  };
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === 'Escape' : !ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', close);
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', close); };
  }, [open]);
  return (
    <span ref={ref} className="relative inline">
      <button
        ref={btn}
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={toggle}
        className="cursor-help border-b border-dotted border-current font-[inherit] text-[inherit] hover:text-brand"
        data-testid={`term-${t}`}
      >
        {children ?? t}
      </button>
      {open && (
        <span id={id} role="note" className={`absolute top-full z-20 mt-1 block w-64 max-w-[calc(100vw-2rem)] ${align === 'right' ? 'right-0 left-auto' : 'left-0'} rounded-md border border-line bg-panel p-2.5 text-left text-xs font-normal normal-case leading-relaxed tracking-normal text-ink shadow-lg`}>
          <span className="font-semibold capitalize">{t}: </span>{GLOSSARY[t]}
        </span>
      )}
    </span>
  );
}
