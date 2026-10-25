'use client';

import { useEffect, useRef } from 'react';

/**
 * Ari's signature illustration: a commit arrives, Ari traces the call path it touches, flags the
 * function, executes a check, proposes a fix and verifies that the path is closed. One timer
 * walks the stages and writes them to `data-s`; every visual change is a CSS transition, so React
 * never re-renders. Paused off-screen; reduced motion shows the finished state without movement.
 */
const STAGES = ['commit', 'trace', 'flag', 'check', 'patch', 'verify'] as const;
const HOLD = [1600, 2200, 1700, 2000, 1900, 3400];

type Node = { id: string; x: number; y: number; label: string; kind?: string };
const NODES: Node[] = [
  { id: 'route', x: 70, y: 124, label: 'GET /payments/{id}', kind: 'route' },
  { id: 'handler', x: 330, y: 124, label: 'api.get_payment' },
  { id: 'service', x: 590, y: 124, label: 'payments.load', kind: 'target' },
  { id: 'query', x: 850, y: 124, label: 'db.payments.by_id' },
  { id: 'auth', x: 330, y: 236, label: 'auth.current_user' },
  { id: 'ledger', x: 590, y: 22, label: 'ledger.balance' },
  { id: 'refunds', x: 850, y: 236, label: 'refunds.create' },
];
const EDGES: Array<[string, string, string]> = [
  ['route', 'handler', 'trace'],
  ['handler', 'service', 'trace'],
  ['service', 'query', 'trace'],
  ['handler', 'auth', ''],
  ['service', 'ledger', ''],
  ['query', 'refunds', ''],
  ['auth', 'service', 'fix'],
];
const W = 170, H = 40;
const at = (id: string) => NODES.find(n => n.id === id)!;

function edgePath(a: Node, b: Node) {
  const ax = a.x + (b.x > a.x ? W : b.x < a.x ? 0 : W / 2), ay = a.y + H / 2;
  const bx = b.x + (b.x > a.x ? 0 : b.x < a.x ? W : W / 2), by = b.y + H / 2;
  if (a.y === b.y) return `M${ax} ${ay} H${bx}`;
  const mx = (ax + bx) / 2;
  return `M${ax} ${ay} C${mx} ${ay} ${mx} ${by} ${bx} ${by}`;
}

export const SIGNAL_LOG: Array<[string, string, string]> = [
  ['commit', 'COMMIT', '2e24b60 · payments: load payment by id'],
  ['trace', 'TRACE', 'route → api.get_payment → payments.load → query'],
  ['flag', 'FLAGGED', 'payments.load returns rows for any owner'],
  ['check', 'VALIDATED', 'Probe, sandbox: Bob reads Alice’s payment, twice'],
  ['patch', 'FIX PROPOSED', 'scope the query to auth.current_user'],
  ['verify', 'VERIFIED', 'Verify, fresh checkout: exploit fails, suite passes'],
];

export function SignalField() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const show = (n: number) => { el.dataset.s = STAGES.slice(0, n + 1).join(' '); };
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) { show(STAGES.length - 1); return; }
    let step = 0, timer = 0, visible = false;
    const tick = () => {
      show(step);
      timer = window.setTimeout(() => { step = (step + 1) % STAGES.length; if (step === 0) el.dataset.s = ''; tick(); }, HOLD[step]);
    };
    el.dataset.s = '';
    const io = new IntersectionObserver(entries => {
      const entry = entries[0];
      if (!entry) return;
      if (entry.isIntersecting && !visible) { visible = true; timer = window.setTimeout(tick, 400); }
      else if (!entry.isIntersecting && visible) { visible = false; window.clearTimeout(timer); }
    });
    io.observe(el);
    return () => { io.disconnect(); window.clearTimeout(timer); };
  }, []);

  return (
    <div ref={ref} className="sf" data-s={STAGES.join(' ')} data-testid="signal-field">
      <div className="sf-stage">
        <svg viewBox="0 0 1090 360" className="sf-svg" aria-hidden="true" focusable="false">
          <defs>
            <pattern id="sf-grid" width="26" height="26" patternUnits="userSpaceOnUse">
              <path d="M26 0H0V26" fill="none" className="sf-grid-line" />
            </pattern>
          </defs>
          <rect width="1090" height="360" fill="url(#sf-grid)" />
          <g className="sf-commits">
            <line x1="0" x2="1090" y1="332" y2="332" className="sf-axis" />
            {Array.from({ length: 24 }, (_, i) => <rect key={i} x={i * 44 + 6} y="324" width="2" height="16" className="sf-tick" />)}
            <rect x="660" y="316" width="3" height="32" className="sf-tick sf-tick-new" />
            <text x="672" y="338" className="sf-mono sf-tick-label">2e24b60</text>
            <path d={`M661 316 C661 240 ${at('service').x + W / 2} 300 ${at('service').x + W / 2} ${at('service').y + H}`} className="sf-arrive" pathLength={1} />
          </g>
          {EDGES.map(([a, b, kind]) => (
            <path key={`${a}-${b}`} d={edgePath(at(a), at(b))} className={`sf-edge ${kind ? `sf-edge-${kind}` : ''}`} pathLength={1} />
          ))}
          <g className="sf-cut"><line x1="784" x2="804" y1="134" y2="154" /><line x1="804" x2="784" y1="134" y2="154" /></g>
          {NODES.map(n => (
            <g key={n.id} className={`sf-node sf-node-${n.id} ${n.kind ? `sf-node-${n.kind}` : ''}`} transform={`translate(${n.x} ${n.y})`}>
              <rect width={W} height={H} rx="3" />
              <text x="12" y="25" className="sf-mono">{n.label}</text>
            </g>
          ))}
        </svg>
        <p className="sf-note">Illustration · not a recorded run</p>
      </div>
      <ol className="sf-log" aria-label="What Ari does with one change">
        {SIGNAL_LOG.map(([stage, state, text], i) => (
          <li key={stage} className={`sf-log-row sf-log-${stage}`}>
            <span className="sf-log-n">{String(i + 1).padStart(2, '0')}</span>
            <span className="sf-log-state">{state}</span>
            <span className="sf-log-text">{text}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
