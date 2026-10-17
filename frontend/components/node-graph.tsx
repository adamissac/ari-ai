'use client';

import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react';
import { num } from '@/lib/format';
import type { LabNodeState, LabScenario } from '@/lib/lab-types';

/**
 * Obsidian-style graph view of a simulated topology: a small force simulation (repulsion,
 * edge springs, centring) keeps the nodes gently floating; hover highlights a node and its
 * neighbours; nodes can be dragged. Visual encodings are observed values only, unless the
 * viewer turns on the clearly labelled ground-truth overlay.
 */

const W = 640;
const H = 340;
const INTERNET = '__internet__';
/** Below this speed (px/frame) every body counts as at rest and the loop stops scheduling frames. */
export const SETTLE_SPEED = 0.02;
/** The ambient drift fades out over this many frames so the layout can come to rest. */
const DRIFT_FRAMES = 300;

/** True once every free body is moving slower than the settle threshold. */
export function isSettled(bodies: { vx: number; vy: number; pinned: boolean }[], threshold = SETTLE_SPEED): boolean {
  return bodies.every(b => b.pinned || Math.hypot(b.vx, b.vy) < threshold);
}

function nodeSummary(name: string, criticality: number | undefined, s: LabNodeState | undefined): string {
  return `${name}: criticality ${criticality ?? 0}, anomaly score ${num(s?.anomaly_score ?? 0, 2)}, alert rate ${num(s?.alert_rate ?? 0, 2)}, monitoring level ${s?.monitoring_level ?? 0}`;
}

interface Body { id: string; x: number; y: number; vx: number; vy: number; pinned: boolean }

function seedBodies(ids: string[]): Body[] {
  return ids.map((id, i) => {
    const a = (i / Math.max(1, ids.length)) * Math.PI * 2;
    return { id, x: W / 2 + Math.cos(a) * 200, y: H / 2 + Math.sin(a) * 110, vx: 0, vy: 0, pinned: false };
  });
}

export function NodeGraph({ scenario, states }: { scenario: LabScenario; states: LabNodeState[] }) {
  const exposed = scenario.nodes.filter(n => n.exposed).map(n => n.name);
  const ids = useMemo(() => [INTERNET, ...scenario.nodes.map(n => n.name)], [scenario]);
  const edges = useMemo<[string, string][]>(() => [...exposed.map(e => [INTERNET, e] as [string, string]), ...scenario.edges], [scenario]); // eslint-disable-line react-hooks/exhaustive-deps
  const bodies = useRef<Body[]>(seedBodies(ids));
  const [snap, setSnap] = useState<Body[]>(() => seedBodies(ids));
  const [hover, setHover] = useState<string | null>(null);
  const [truth, setTruth] = useState(false);
  const [dragging, setDragging] = useState(false);
  const drag = useRef<{ id: string; dx: number; dy: number } | null>(null);
  const wake = useRef<() => void>(() => {});
  const svg = useRef<SVGSVGElement>(null);

  useEffect(() => { bodies.current = seedBodies(ids); }, [ids]);

  useEffect(() => {
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let frame = 0;
    let t = 0;
    let calm = 0;
    const tick = () => {
      frame = 0;
      t += 1;
      const bs = bodies.current;
      const byId = new Map(bs.map(b => [b.id, b]));
      for (const a of bs) {
        let fx = (W / 2 - a.x) * 0.0025;
        let fy = (H / 2 - a.y) * 0.004;
        for (const b of bs) {
          if (a === b) continue;
          const dx = a.x - b.x; const dy = a.y - b.y;
          const d2 = Math.max(dx * dx + dy * dy, 400);
          const f = 5200 / d2;
          const d = Math.sqrt(d2);
          fx += (dx / d) * f; fy += (dy / d) * f;
        }
        for (const [u, v] of edges) {
          const other = u === a.id ? byId.get(v) : v === a.id ? byId.get(u) : undefined;
          if (!other) continue;
          const dx = other.x - a.x; const dy = other.y - a.y;
          const d = Math.max(1, Math.hypot(dx, dy));
          const k = (d - 175) * 0.01;
          fx += (dx / d) * k; fy += (dy / d) * k;
        }
        if (!reduced && t < DRIFT_FRAMES) {
          const fade = 1 - t / DRIFT_FRAMES;
          fx += Math.sin(t * 0.013 + a.x * 0.05) * 0.03 * fade; fy += Math.cos(t * 0.011 + a.y * 0.05) * 0.03 * fade;
        }
        if (!a.pinned) {
          a.vx = (a.vx + fx) * 0.82; a.vy = (a.vy + fy) * 0.82;
          a.x = Math.min(W - 40, Math.max(40, a.x + a.vx));
          a.y = Math.min(H - 40, Math.max(36, a.y + a.vy));
        }
      }
      setSnap(bs.map(b => ({ ...b })));
      calm = isSettled(bs) ? calm + 1 : 0;
      if (calm < 10 && (!reduced || t < 240)) frame = requestAnimationFrame(tick);
    };
    wake.current = () => { calm = 0; if (!frame) frame = requestAnimationFrame(tick); };
    wake.current();
    return () => { cancelAnimationFrame(frame); frame = 0; wake.current = () => {}; };
  }, [edges]);

  const toSvg = (e: ReactPointerEvent) => {
    const m = svg.current?.getScreenCTM();
    if (!m) return { x: 0, y: 0 };
    const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(m.inverse());
    return { x: p.x, y: p.y };
  };
  const onDown = (id: string) => (e: ReactPointerEvent<SVGGElement>) => {
    const b = bodies.current.find(x => x.id === id);
    if (!b) return;
    const p = toSvg(e);
    drag.current = { id, dx: b.x - p.x, dy: b.y - p.y };
    b.pinned = true;
    setDragging(true);
    wake.current();
    (e.target as Element).setPointerCapture?.(e.pointerId);
  };
  const onMove = (e: ReactPointerEvent<SVGSVGElement>) => {
    if (!drag.current) return;
    const b = bodies.current.find(x => x.id === drag.current!.id);
    if (!b) return;
    const p = toSvg(e);
    b.x = Math.min(W - 30, Math.max(30, p.x + drag.current.dx));
    b.y = Math.min(H - 30, Math.max(30, p.y + drag.current.dy));
    b.vx = 0; b.vy = 0;
    wake.current();
  };
  const onUp = () => {
    const b = drag.current && bodies.current.find(x => x.id === drag.current!.id);
    if (b) b.pinned = false;
    drag.current = null;
    setDragging(false);
    wake.current();
  };

  const pos = new Map(snap.map(b => [b.id, b]));
  const state = new Map(states.map(s => [s.node, s]));
  const meta = new Map(scenario.nodes.map(n => [n.name, n]));
  const neighbours = new Set<string>();
  if (hover) { neighbours.add(hover); for (const [u, v] of edges) { if (u === hover) neighbours.add(v); if (v === hover) neighbours.add(u); } }
  const dim = (id: string) => hover !== null && !neighbours.has(id);
  const hovered = hover && hover !== INTERNET ? { node: meta.get(hover), s: state.get(hover) } : null;

  return (
    <div className="graph-view relative overflow-hidden rounded-xl">
      <svg
        ref={svg}
        viewBox={`0 0 ${W} ${H}`}
        className="block h-auto w-full select-none"
        style={{ touchAction: dragging ? 'none' : 'pan-y' }}
        role="group"
        aria-label={`Simulated topology for ${scenario.name}`}
        data-testid="topology"
        onPointerMove={onMove}
        onPointerUp={onUp}
        onPointerCancel={onUp}
        onPointerLeave={() => { onUp(); setHover(null); }}
      >
        <defs>
          <pattern id="graph-dots" width="18" height="18" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="0.8" fill="rgba(255,255,255,0.08)" /></pattern>
          <radialGradient id="graph-glow"><stop offset="0%" stopColor="#c2452d" stopOpacity="0.55" /><stop offset="100%" stopColor="#c2452d" stopOpacity="0" /></radialGradient>
        </defs>
        <rect width={W} height={H} fill="url(#graph-dots)" />

        {edges.map(([u, v]) => {
          const a = pos.get(u); const b = pos.get(v);
          if (!a || !b) return null;
          const hot = hover !== null && neighbours.has(u) && neighbours.has(v) && (u === hover || v === hover);
          const limited = state.get(v)?.rate_limited || state.get(u)?.rate_limited;
          const heat = Math.max(state.get(u)?.anomaly_score ?? 0, state.get(v)?.anomaly_score ?? 0);
          return (
            <line
              key={u + '>' + v}
              x1={a.x} y1={a.y} x2={b.x} y2={b.y}
              className="graph-edge"
              data-hot={hot || undefined}
              data-dim={(hover !== null && !hot) || undefined}
              data-flow={heat > 0.5 || undefined}
              strokeDasharray={limited ? '3 5' : heat > 0.5 ? '2 6' : undefined}
            />
          );
        })}

        {ids.map(id => {
          const b = pos.get(id);
          if (!b) return null;
          if (id === INTERNET) {
            return (
              <g key={id} transform={`translate(${b.x},${b.y})`} className="graph-node" data-dim={dim(id) || undefined}
                tabIndex={0} role="img" aria-label="internet, outside the network" style={{ touchAction: 'none' }}
                onFocus={() => setHover(id)} onBlur={() => setHover(null)}
                onPointerEnter={() => setHover(id)} onPointerLeave={() => setHover(null)} onPointerDown={onDown(id)}>
                <circle r={10} className="graph-internet" />
                <text y={24} textAnchor="middle" className="graph-label">internet</text>
              </g>
            );
          }
          const n = meta.get(id);
          const s = state.get(id);
          const heat = Math.min(1, s?.anomaly_score ?? 0);
          const r = 10 + (n?.criticality ?? 1) * 3;
          const stage = s?.hidden_stage_ground_truth ?? 'none';
          return (
            <g key={id} transform={`translate(${b.x},${b.y})`} className="graph-node" data-dim={dim(id) || undefined} data-hover={hover === id || undefined}
              tabIndex={0} role="img" aria-label={nodeSummary(n?.name ?? id, n?.criticality, s)} style={{ touchAction: 'none' }}
              onFocus={() => setHover(id)} onBlur={() => setHover(null)}
              onPointerEnter={() => setHover(id)} onPointerLeave={() => setHover(null)} onPointerDown={onDown(id)}>
              {heat > 0.05 && <circle r={r * (1.8 + heat * 1.6)} fill="url(#graph-glow)" opacity={0.35 + heat * 0.65} />}
              {truth && stage !== 'none' && <circle r={r + 9} className="graph-truth" />}
              <circle r={r} className="graph-dot" style={{ fill: `color-mix(in srgb, #c2452d ${Math.round(15 + heat * 85)}%, #8a7a75)` }} />
              {s?.isolated && <circle r={r + 4} className="graph-isolated" />}
              {n?.exposed && <circle r={r + (s?.isolated ? 8 : 4)} className="graph-exposed" />}
              <text y={r + 15} textAnchor="middle" className="graph-label">{id}</text>
              {truth && stage !== 'none' && <text y={-r - 8} textAnchor="middle" className="graph-truth-label">{stage}</text>}
            </g>
          );
        })}
      </svg>

      <table className="sr-only">
        <caption>Current values for each node in {scenario.name}</caption>
        <thead><tr><th scope="col">Node</th><th scope="col">Criticality</th><th scope="col">Anomaly score</th><th scope="col">Alert rate</th><th scope="col">Monitoring level</th><th scope="col">Status</th></tr></thead>
        <tbody>
          {scenario.nodes.map(n => {
            const s = state.get(n.name);
            const status = [n.exposed && 'internet-exposed', s?.isolated && 'isolated', s?.rate_limited && 'rate-limited', s?.reassessment_pending && 'reassessment pending'].filter(Boolean).join(', ') || 'no defensive action';
            return (
              <tr key={n.name}>
                <th scope="row">{n.name}</th><td>{n.criticality}</td><td>{num(s?.anomaly_score ?? 0, 2)}</td><td>{num(s?.alert_rate ?? 0, 2)}</td><td>{s?.monitoring_level ?? 0}</td><td>{status}</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {hovered?.node && (
        <div className="graph-card pointer-events-none absolute bottom-3 left-3 w-52 rounded-lg p-3 text-xs" aria-hidden="true">
          <p className="font-mono text-sm text-white">{hovered.node.name}</p>
          <dl className="mt-2 grid grid-cols-[1fr_auto] gap-x-3 gap-y-0.5 text-white/70">
            <dt>criticality</dt><dd className="font-mono text-white">{hovered.node.criticality}</dd>
            <dt>anomaly score</dt><dd className="font-mono text-white">{num(hovered.s?.anomaly_score ?? 0, 2)}</dd>
            <dt>alert rate</dt><dd className="font-mono text-white">{num(hovered.s?.alert_rate ?? 0, 2)}</dd>
            <dt>monitoring</dt><dd className="font-mono text-white">{hovered.s?.monitoring_level ?? 0}</dd>
          </dl>
          <p className="mt-2 text-white/60">
            {[hovered.node.exposed && 'internet-exposed', hovered.s?.isolated && 'isolated', hovered.s?.rate_limited && 'rate-limited', hovered.s?.reassessment_pending && 'reassessment pending'].filter(Boolean).join(' · ') || 'no defensive action'}
          </p>
        </div>
      )}

      <label className="graph-toggle absolute right-3 top-3 flex cursor-pointer items-center gap-2 rounded-md px-2.5 py-1.5 text-xs text-white/80">
        <input type="checkbox" checked={truth} onChange={e => setTruth(e.target.checked)} className="accent-[var(--color-brand)]" />
        Show attacker (ground truth)
      </label>
    </div>
  );
}
