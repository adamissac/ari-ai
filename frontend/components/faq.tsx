'use client';

import { useId, useState } from 'react';

/** FAQ accordion (kairo.security pattern): one row per question, answer slides open. */
export function Faq({ items }: { items: ReadonlyArray<{ q: string; a: string }> }) {
  const [open, setOpen] = useState<number | null>(null);
  const base = useId();
  return (
    <ul className="faq">
      {items.map((item, i) => {
        const isOpen = open === i;
        const panel = `${base}-panel-${i}`;
        return (
          <li key={item.q} className="faq-item" data-open={isOpen || undefined}>
            <h3>
              <button type="button" className="faq-q" aria-expanded={isOpen} aria-controls={panel} onClick={() => setOpen(isOpen ? null : i)}>
                <span>{item.q}</span>
                <span aria-hidden="true" className="faq-icon" />
              </button>
            </h3>
            <div id={panel} role="region" aria-label={item.q} aria-hidden={!isOpen} className="faq-a">
              <div className="faq-a-inner"><p>{item.a}</p></div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
