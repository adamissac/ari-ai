'use client';

import { useCallback, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent as ReactPointerEvent } from 'react';
import { num } from '@/lib/format';
import type { LabNodeState, LabScenario } from '@/lib/lab-types';
import { INTERNET, nodeStatusLine, nodeViews, parseAction, type NodeView, type ServiceKind } from '@/lib/lab-story';

/**
 * Network map of a simulated scenario (Defense Lab). The layout is stable (columns from the
 * internet inwards along the recorded topology), so nodes never drift during replay. Every
 * visual state comes from observed values in the bundle; the hidden attacker stage is drawn
 * only when the viewer turns on the clearly labelled ground-truth overlay. A visually hidden
 * table repeats every node value for assistive technology.
 */

const W = 1080;
const H = 480;
export const INTERNET_ID = '__internet__';

type Point = { x: number; y: number };

/** Columns: internet, then breadth-first depth from internet-exposed services. */
export function layoutNetwork(scenario: LabScenario): Map<string, Point> {
  const depth = new Map<string, number>();
  const queue = scenario.nodes.filter(n => n.exposed).map(n => n.name);
  queue.forEach(n => depth.set(n, 0));
  while (queue.length) {
    const cur = queue.shift() as string;
    for (const [a, b] of scenario.edges) {
      const next = a === cur ? b : b === cur ? a : null;
      if (next && !depth.has(next)) { depth.set(next, (depth.get(cur) ?? 0) + 1); queue.push(next); }
    }
  }
  scenario.nodes.forEach(n => { if (!depth.has(n.name)) depth.set(n.name, 0); });
  const cols = new Map<number, string[]>();
  for (const n of scenario.nodes) { const d = depth.get(n.name) ?? 0; cols.set(d, [...(cols.get(d) ?? []), n.name]); }
  const maxD = Math.max(0, ...cols.keys());
  const x0 = 100; const x1 = W - 110;
  const step = (x1 - x0) / (maxD + 1);
  const pos = new Map<string, Point>();
  pos.set(INTERNET_ID, { x: x0, y: H / 2 });
  for (const [d, names] of cols) names.forEach((name, i) => pos.set(name, { x: x0 + step * (d + 1), y: ((i + 1) * H) / (names.length + 1) }));
  return pos;
}

function Icon({ kind }: { kind: ServiceKind }) {
  const p = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.6, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };
  switch (kind) {
    case 'internet': return <g {...p}><circle cx="0" cy="0" r="8" /><path d="M-8 0h16M0-8c3 3 3 13 0 16M0-8c-3 3-3 13 0 16" /></g>;
    case 'gateway': return <g {...p}><path d="M-7 8V-3l7-5 7 5V8" /><path d="M-3 8V2h6v6" /></g>;
    case 'api': return <g {...p}><path d="M-3-7c-3 0-3 2-3 4s-2 3-2 3 2 1 2 3 0 4 3 4M3-7c3 0 3 2 3 4s2 3 2 3-2 1-2 3 0 4-3 4" /></g>;
    case 'auth': return <g {...p}><rect x="-6" y="-1" width="12" height="9" rx="2" /><path d="M-3.5-1v-3a3.5 3.5 0 0 1 7 0v3" /></g>;
    case 'payments': return <g {...p}><rect x="-8" y="-6" width="16" height="12" rx="2" /><path d="M-8-2h16M-5 3h4" /></g>;
    case 'database': return <g {...p}><ellipse cx="0" cy="-5" rx="7" ry="2.6" /><path d="M-7-5v10c0 1.4 3.1 2.6 7 2.6S7 6.4 7 5V-5M-7 0c0 1.4 3.1 2.6 7 2.6S7 1.4 7 0" /></g>;
    case 'web': return <g {...p}><rect x="-8" y="-6" width="16" height="12" rx="2" /><path d="M-8-2h16" /></g>;
    case 'monitoring': return <g {...p}><path d="M-8 1h4l2-5 3 9 2-4h5" /></g>;
    default: return <g {...p}><rect x="-6" y="-6" width="12" height="12" rx="2" /></g>;
  }
}

type BadgeKind = 'watch' | 'slow' | 'cut' | 'recheck';
const BADGE_TITLE: Record<BadgeKind, string> = { watch: 'Watched closely', slow: 'Traffic slowed', cut: 'Cut off from the network', recheck: 'Re-check requested' };

/** Small state badge drawn beside a node. Exported so the legend uses identical marks. */
export function StateBadge({ kind, x = 0, y = 0 }: { kind: BadgeKind; x?: number; y?: number }) {
  const p = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.5, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };
  return (
    <g transform={`translate(${x},${y})`} className={`map-badge map-badge-${kind}`}>
      <title>{BADGE_TITLE[kind]}</title>
      <circle r="9" />
      {kind === 'watch' && <g {...p}><path d="M-5 0c2-3.2 8-3.2 10 0-2 3.2-8 3.2-10 0z" /><circle r="1.4" /></g>}
      {kind === 'slow' && <g {...p}><path d="M-4.5 3a5 5 0 1 1 9 0" /><path d="M0 2.5l2.5-3.5" /></g>}
      {kind === 'cut' && <g {...p}><path d="M-4-4l8 8M4-4l-8 8" /></g>}
      {kind === 'recheck' && <g {...p}><path d="M4 -2.5A4.6 4.6 0 1 0 4.4 2" /><path d="M4.5-5v3h-3" /></g>}
    </g>
  );
}

function badgesFor(v: NodeView): BadgeKind[] {
  const out: BadgeKind[] = [];
  if (v.isolated) out.push('cut'); else if (v.rateLimited) out.push('slow');
  if (v.watching) out.push('watch');
  if (v.recheck) out.push('recheck');
  return out;
}

export interface NetworkMapProps {
  scenario: LabScenario;
  states: LabNodeState[];
  /** Recorded action at the current step, e.g. "isolate:api". */
  action?: string;
  /** Current step; restarts the one-shot action highlight. */
  t?: number;
  selected?: string | null;
  onSelect?: (node: string | null) => void;
  showTruth?: boolean;
}

export function NodeGraph({ scenario, states, action = 'noop', t = 0, selected = null, onSelect = () => {}, showTruth = false }: NetworkMapProps) {
  const base = useMemo(() => layoutNetwork(scenario), [scenario]);
  const [moved, setMoved] = useState<Map<string, Point>>(new Map());
  const [view, setView] = useState({ k: 1, x: 0, y: 0 });
  const [hover, setHover] = useState<string | null>(null);
  const svg = useRef<SVGSVGElement>(null);
  const drag = useRef<{ id: string | null; sx: number; sy: number; ox: number; oy: number; moved: boolean } | null>(null);

  const pos = (id: string): Point => moved.get(id) ?? base.get(id) ?? { x: W / 2, y: H / 2 };
  const views = nodeViews(scenario, states);
  const byName = new Map(views.map(v => [v.name, v]));
  const stateBy = new Map(states.map(s => [s.node, s]));
  const exposed = scenario.nodes.filter(n => n.exposed).map(n => n.name);
  const edges: [string, string][] = [...exposed.map(e => [INTERNET_ID, e] as [string, string]), ...scenario.edges];
  const target = action.startsWith('noop') ? null : parseAction(action).node;
  const focus = selected ?? hover;
  const neighbours = new Set<string>();
  if (focus) { neighbours.add(focus); for (const [a, b] of edges) { if (a === focus) neighbours.add(b); if (b === focus) neighbours.add(a); } }
  const crit = new Map(scenario.nodes.map(n => [n.name, n.criticality]));
  const maxCrit = Math.max(1e-9, ...scenario.nodes.map(n => n.criticality));
  const radius = (name: string) => 22 + ((crit.get(name) ?? 0) / maxCrit) * 12;

  const toSvg = useCallback((e: { clientX: number; clientY: number }) => {
    const m = svg.current?.getScreenCTM?.();
    if (!m || typeof DOMPoint === 'undefined') return { x: e.clientX, y: e.clientY };
    const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(m.inverse());
    return { x: p.x, y: p.y };
  }, []);

  const onPointerDown = (e: ReactPointerEvent) => {
    if (e.button !== 0) return;
    const id = (e.currentTarget as Element).getAttribute('data-node');
    const p = toSvg(e);
    const start = id ? pos(id) : { x: view.x, y: view.y };
    drag.current = { id, sx: p.x, sy: p.y, ox: start.x, oy: start.y, moved: false };
    // Touch keeps the page scrollable (touch-action: pan-y): nodes are tap-to-select only.
    if (e.pointerType !== 'touch') (e.currentTarget as Element).setPointerCapture?.(e.pointerId);
    e.stopPropagation();
  };
  const onPointerMove = (e: ReactPointerEvent) => {
    const d = drag.current;
    if (!d || e.pointerType === 'touch') return;
    const p = toSvg(e);
    const dx = p.x - d.sx; const dy = p.y - d.sy;
    if (!d.moved && Math.hypot(dx, dy) < 4) return;
    d.moved = true;
    if (d.id) {
      const id = d.id;
      setMoved(m => new Map(m).set(id, { x: Math.min(W - 30, Math.max(30, d.ox + dx / view.k)), y: Math.min(H - 30, Math.max(30, d.oy + dy / view.k)) }));
    } else setView(v => ({ ...v, x: d.ox + dx, y: d.oy + dy }));
  };
  const onPointerUp = () => {
    const d = drag.current;
    drag.current = null;
    if (!d || d.moved) return;
    if (d.id === null) onSelect(null);
    else if (d.id !== INTERNET_ID) onSelect(selected === d.id ? null : d.id);
  };
  const zoom = (f: number) => setView(v => {
    const k = Math.min(2.5, Math.max(0.6, v.k * f));
    return { k, x: W / 2 - ((W / 2 - v.x) * k) / v.k, y: H / 2 - ((H / 2 - v.y) * k) / v.k };
  });
  const reset = () => { setView({ k: 1, x: 0, y: 0 }); setMoved(new Map()); };

  const order = views.map(v => v.name);
  const focusNode = (name: string) => requestAnimationFrame(() => svg.current?.querySelector<SVGGElement>(`[data-node="${CSS.escape(name)}"]`)?.focus());
  const onKey = (name: string) => (e: KeyboardEvent) => {
    const i = order.indexOf(name);
    const go = (n: string | undefined) => { if (n) { onSelect(n); focusNode(n); } };
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(selected === name ? null : name); }
    else if (e.key === 'ArrowRight' || e.key === 'ArrowDown') { e.preventDefault(); go(order[(i + 1) % order.length]); }
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') { e.preventDefault(); go(order[(i - 1 + order.length) % order.length]); }
    else if (e.key === 'Escape') onSelect(null);
  };

  const hovered = hover && hover !== INTERNET_ID ? byName.get(hover) : null;
  const tip = hovered ? pos(hovered.name) : null;

  return (
    <div className="net-map" data-truth={showTruth || undefined}>
      <div className="network-heading"><span className="network-eyebrow">NETWORK / RECORDED STEP {t}</span><span>Follow the connections. Select a service to look inside.</span></div>
      <div className="network-actors">
        <div><span className="actor-dot actor-threat" /><span><b>Attacker location</b><small>{showTruth ? states.filter(s => s.hidden_stage_ground_truth !== 'none').map(s => byName.get(s.node)?.info.label ?? s.node).join(', ') || 'Not inside the network at this step' : 'Hidden — turn on replay ground truth to see it'}</small></span></div>
        <div><span className="actor-dot actor-guard" /><span><b>Defender location</b><small>{target ? `${byName.get(target)?.info.label ?? target} · ${parseAction(action).verb.replaceAll('_', ' ')}` : action === 'escalate_to_human' ? 'Calling a person for help' : 'Watching the network; no move this step'}</small></span></div>
      </div>
      <div className="net-scroll">
      <div className="net-canvas">
      <svg
        ref={svg}
        viewBox={`0 0 ${W} ${H}`}
        className="net-svg"
        style={{ touchAction: 'pan-y' }}
        role="group"
        aria-label={`Simulated network for ${scenario.name}: ${views.length} services. Tab to a service and use the arrow keys to move between them.`}
        data-testid="topology"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={() => { drag.current = null; setHover(null); }}
        onWheel={e => { if (e.ctrlKey || e.metaKey) { e.preventDefault(); zoom(e.deltaY < 0 ? 1.1 : 0.9); } }}
      >
        <defs>
          <pattern id="net-dots" width="20" height="20" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="0.9" fill="rgba(255,255,255,0.07)" /></pattern>
          <radialGradient id="net-hot"><stop offset="0%" stopColor="#c2452d" stopOpacity="0.42" /><stop offset="100%" stopColor="#c2452d" stopOpacity="0" /></radialGradient>
        </defs>
        <rect width={W} height={H} fill="url(#net-dots)" />
        <text x="28" y="30" className="network-zone">OUTSIDE</text><text x="260" y="30" className="network-zone">YOUR APPLICATION</text>
        <line x1="205" x2="205" y1="48" y2={H - 20} className="network-boundary" />
        <g transform={`translate(${view.x} ${view.y}) scale(${view.k})`}>
          {edges.map(([a, b]) => {
            const p = pos(a); const q = pos(b);
            const va = byName.get(a); const vb = byName.get(b);
            const cut = va?.isolated || vb?.isolated;
            const slow = !cut && (va?.rateLimited || vb?.rateLimited);
            const lit = focus !== null && (a === focus || b === focus);
            const acted = target !== null && (a === target || b === target);
            const mx = (p.x + q.x) / 2; const my = (p.y + q.y) / 2;
            const bend = Math.abs(p.x - q.x) < 1 ? 46 : 0; // same-column links bow out so they stay visible
            const d = `M${p.x},${p.y} Q${mx + bend},${my} ${q.x},${q.y}`;
            const iso = va?.isolated ? p : q; const other = va?.isolated ? q : p;
            return (
              <g key={`${a}>${b}`}>
                <path d={d} className="net-edge" data-cut={cut || undefined} data-slow={slow || undefined} data-lit={lit || undefined} data-dim={(focus !== null && !lit) || undefined} />
                {acted && <path key={`flash-${t}`} d={d} className="net-edge-flash" pathLength={1} />}
                {cut && <g transform={`translate(${iso.x + (other.x - iso.x) * 0.3},${iso.y + (other.y - iso.y) * 0.3})`} className="net-cut"><circle r="6" /><path d="M-3-3l6 6M3-3l-6 6" /></g>}
              </g>
            );
          })}

          {(() => {
            const p = pos(INTERNET_ID);
            return (
              <g transform={`translate(${p.x},${p.y})`} className="net-node net-internet" data-dim={(focus !== null && !neighbours.has(INTERNET_ID)) || undefined}
                onPointerEnter={() => setHover(INTERNET_ID)} onPointerLeave={() => setHover(null)}>
                <title>{INTERNET.role}</title>
                <rect x="-68" y="-42" width="136" height="104" rx="12" className="network-card" /><circle r="20" className="net-body" />
                <g className="net-icon"><Icon kind="internet" /></g>
                <text y="38" textAnchor="middle" className="net-label">Internet</text>
                <text y="51" textAnchor="middle" className="net-sub">outside traffic</text>
              </g>
            );
          })()}

          {views.map(v => {
            const p = pos(v.name);
            const r = radius(v.name);
            const stage = stateBy.get(v.name)?.hidden_stage_ground_truth ?? 'none';
            const isTarget = target === v.name;
            return (
              <g
                key={v.name}
                data-node={v.name}
                transform={`translate(${p.x},${p.y})`}
                className="net-node"
                data-signal={v.signal}
                data-isolated={v.isolated || undefined}
                data-selected={selected === v.name || undefined}
                data-dim={(focus !== null && !neighbours.has(v.name)) || undefined}
                role="button"
                tabIndex={0}
                aria-pressed={selected === v.name}
                aria-label={`${v.info.label} (${v.name})${v.critical ? ', critical' : ''}${v.exposed ? ', internet-exposed' : ''}: ${nodeStatusLine(v)}`}
                onPointerDown={onPointerDown}
                onPointerEnter={() => setHover(v.name)}
                onPointerLeave={() => setHover(h => (h === v.name ? null : h))}
                onFocus={() => setHover(v.name)}
                onBlur={() => setHover(h => (h === v.name ? null : h))}
                onKeyDown={onKey(v.name)}
              >
                {/* Everything about a node stays inside its card, so stacked nodes never collide. */}
                <rect x={-82} y={-60} width={164} height={132} rx={14} className="network-card" />
                {v.signal === 'high' && <circle r={r * 2.1} fill="url(#net-hot)" className="net-glow" />}
                {showTruth && stage !== 'none' && <circle r={r + 12} className="net-truth" />}
                {isTarget && <circle key={`act-${t}`} r={r + 6} className="net-act" />}
                <circle r={r + 4} className="net-ring" />
                <circle r={r} className="net-body" />
                <g className="net-icon" transform={`scale(${(r / 24).toFixed(3)})`}><Icon kind={v.info.kind} /></g>
                {badgesFor(v).map((b, i) => <StateBadge key={b} kind={b} x={r * 0.8} y={-r * 0.8 + i * 20} />)}
                <text y={r + 20} textAnchor="middle" className="net-label">{v.info.label}</text>
                {showTruth && stage !== 'none'
                  ? <text y={r + 34} textAnchor="middle" className="net-truth-label">attacker: {stage}</text>
                  : v.critical && <text y={r + 34} textAnchor="middle" className="net-sub">Critical</text>}
                {showTruth && stage !== 'none' && <g transform="translate(-76,-54)" className="network-intruder"><rect width="74" height="17" rx="8.5" /><text x="37" y="11.8" textAnchor="middle">{v.isolated ? 'ATTACKER CUT OFF' : 'ATTACKER HERE'}</text></g>}
                {isTarget && <g transform="translate(2,-54)" className="network-defender"><rect width="74" height="17" rx="8.5" /><text x="37" y="11.8" textAnchor="middle">DEFENDER HERE</text></g>}
              </g>
            );
          })}
        </g>
      </svg>

      {hovered && tip && (
        <div className="net-tip" style={{ left: `${((tip.x * view.k + view.x) / W) * 100}%`, top: `${((tip.y * view.k + view.y) / H) * 100}%` }} aria-hidden="true">
          <p className="font-medium text-white">{hovered.info.label}</p>
          <p className="text-white/70">{nodeStatusLine(hovered)}</p>
        </div>
      )}
      </div>
      </div>

      <div className="net-tools" role="toolbar" aria-label="Map view">
        <button type="button" onClick={() => zoom(1.2)} aria-label="Zoom in">+</button>
        <button type="button" onClick={() => zoom(1 / 1.2)} aria-label="Zoom out">−</button>
        <button type="button" onClick={reset} aria-label="Reset view">Fit</button>
      </div>
      {showTruth && <p className="net-truth-chip" role="note">Showing hidden simulation truth — the defender cannot see this</p>}

      <table className="sr-only">
        <caption>Observed values per service at this step</caption>
        <thead><tr><th scope="col">Service</th><th scope="col">Anomaly score</th><th scope="col">Alert rate</th><th scope="col">Monitoring level</th><th scope="col">State</th></tr></thead>
        <tbody>
          {views.map(v => {
            const s = stateBy.get(v.name);
            return (
              <tr key={v.name}>
                <th scope="row">{v.name}</th>
                <td>{num(s?.anomaly_score ?? 0, 2)}</td>
                <td>{num(s?.alert_rate ?? 0, 2)}</td>
                <td>{s?.monitoring_level ?? 0}</td>
                <td>{nodeStatusLine(v).toLowerCase()}{v.isolated ? ' (isolated)' : ''}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
