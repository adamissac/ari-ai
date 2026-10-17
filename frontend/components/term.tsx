'use client';

import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { GLOSSARY, type GlossaryTerm } from '@/lib/glossary';

/** A jargon word with an inline definition that opens on click/Enter and closes on Escape or blur. */
export function Term({ t, children }: { t: GlossaryTerm; children?: ReactNode }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const ref = useRef<HTMLSpanElement>(null);
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
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen(o => !o)}
        className="cursor-help border-b border-dotted border-current font-[inherit] text-[inherit] hover:text-brand"
        data-testid={`term-${t}`}
      >
        {children ?? t}
      </button>
      {open && (
        <span id={id} role="note" className="absolute left-0 top-full z-20 mt-1 block w-64 rounded-md border border-line bg-panel p-2.5 text-left text-xs font-normal normal-case leading-relaxed tracking-normal text-ink shadow-lg">
          <span className="font-semibold capitalize">{t}: </span>{GLOSSARY[t]}
        </span>
      )}
    </span>
  );
}
