'use client';

import { useMemo, useState } from 'react';

/**
 * Continuous-defense map (docs/14 "Preferred visualization structure"): the components under
 * watch, their dependencies, a state per node and how recently it was checked. Critical
 * components are named in words, not colour alone. The caller decides whether the states are
 * recorded or simulated and must say so next to the map.
 */
export type MapState = 'healthy' | 'checking' | 'attention' | 'limited' | 'hardened' | 'isolated';
export interface MapNode { id: string; label: string; kind: string; critical: boolean }

export const MAP_STATE: Record<MapState, { label: string; glyph: string; color: string }> = {
  healthy: { label: 'Healthy', glyph: '●', color: '#5fc48d' },
  checking: { label: 'Being checked', glyph: '◌', color: '#e0735c' },
  attention: { label: 'Needs attention', glyph: '▲', color: '#f0a43a' },
  limited: { label: 'Rate-limited', glyph: '◐', color: '#e8c07a' },
  hardened: { label: 'Hardened', glyph: '◆', color: '#7fd1ae' },
  isolated: { label: 'Isolated', glyph: '■', color: '#c9b8b2' },
};

const W = 1000;
const NODE_W = 150;
const NODE_H = 54;
const ROW = 74;

/** Canvas height that fits the tallest column with room between rows. */
export function mapHeight(layout: Map<string, { x: number; y: number }>): number {
  return Math.max(...[...layout.values()].map(p => p.y), 0) + NODE_H / 2 + 28;
}

/** Columns by shortest distance from the first node; nodes with no path go last. */
export function layoutLayers(nodes: readonly MapNode[], links: readonly [string, string][]): Map<string, { x: number; y: number }> {
  const depth = new Map<string, number>();
  if (nodes[0]) depth.set(nodes[0].id, 0);
  const queue = nodes[0] ? [nodes[0].id] : [];
  while (queue.length) {
    const id = queue.shift()!;
    for (const [a, b] of links) {
      const next = a === id ? b : b === id ? a : null;
      if (next && !depth.has(next)) { depth.set(next, depth.get(id)! + 1); queue.push(next); }
    }
  }
  const maxDepth = Math.max(0, ...depth.values());
  for (const node of nodes) if (!depth.has(node.id)) depth.set(node.id, maxDepth + 1);
  const columns = Math.max(...depth.values()) + 1;
  const byColumn = new Map<number, string[]>();
  for (const node of nodes) byColumn.set(depth.get(node.id)!, [...(byColumn.get(depth.get(node.id)!) ?? []), node.id]);
  const tallest = Math.max(...[...byColumn.values()].map(ids => ids.length));
  const height = Math.max(220, tallest * ROW + 40);
  const out = new Map<string, { x: number; y: number }>();
  for (const [column, ids] of byColumn) {
    ids.forEach((id, i) => {
      const x = columns === 1 ? W / 2 : 40 + NODE_W / 2 + (column * (W - 80 - NODE_W)) / (columns - 1);
      const y = height / 2 + (i - (ids.length - 1) / 2) * ROW;
      out.set(id, { x, y });
    });
  }
  return out;
}

export function DefenseMap({
  nodes, links, states, checkedMinutesAgo, title = 'Components under watch', footnote,
}: {
  nodes: readonly MapNode[];
  links: readonly [string, string][];
  states: Record<string, MapState>;
  checkedMinutesAgo?: Record<string, number>;
  title?: string;
  footnote?: string;
}) {
  const pos = useMemo(() => layoutLayers(nodes, links), [nodes, links]);
  const H = mapHeight(pos);
  const [hover, setHover] = useState<string | null>(null);
  const near = (id: string) => hover === null || hover === id || links.some(([a, b]) => (a === hover && b === id) || (b === hover && a === id));
  const counts = nodes.reduce<Record<string, number>>((acc, node) => ({ ...acc, [states[node.id] ?? 'healthy']: (acc[states[node.id] ?? 'healthy'] ?? 0) + 1 }), {});

  return (
    <figure className="defense-map" data-testid="defense-map">
      <figcaption className="flex flex-wrap items-center justify-between gap-3 px-5 pt-4">
        <span className="label-mono text-white/60">{title}</span>
        <span className="flex flex-wrap gap-3 text-xs">
          {(Object.keys(MAP_STATE) as MapState[]).filter(s => counts[s]).map(s => (
            <span key={s} className="flex items-center gap-1.5 text-white/75"><span aria-hidden="true" style={{ color: MAP_STATE[s].color }}>{MAP_STATE[s].glyph}</span>{counts[s]} {MAP_STATE[s].label.toLowerCase()}</span>
          ))}
        </span>
      </figcaption>
      <div className="overflow-x-auto">
        <svg viewBox={`0 0 ${W} ${H}`} className="mx-auto block h-auto w-full min-w-[640px] max-w-[1100px]" role="img" aria-label={`${title}: ${nodes.map(n => `${n.label} ${MAP_STATE[states[n.id] ?? 'healthy'].label}${n.critical ? ', critical' : ''}`).join('; ')}`}>
          <defs>
            <pattern id="dm-grid" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" fill="none" stroke="rgba(255,255,255,0.045)" /></pattern>
          </defs>
          <rect width={W} height={H} fill="url(#dm-grid)" />
          {links.map(([a, b]) => {
            const p = pos.get(a); const q = pos.get(b);
            if (!p || !q) return null;
            const mid = (p.x + q.x) / 2;
            const d = `M${p.x} ${p.y} C${mid} ${p.y} ${mid} ${q.y} ${q.x} ${q.y}`;
            const hot = [states[a], states[b]].some(x => x === 'checking' || x === 'attention' || x === 'limited');
            return (
              <g key={`${a}-${b}`} opacity={near(a) && near(b) ? 1 : 0.2} className="transition-opacity duration-200">
                <path d={d} className="dm-link" />
                <path d={d} className={hot ? 'dm-flow dm-flow-hot' : 'dm-flow'} />
              </g>
            );
          })}
          {nodes.map(node => {
            const p = pos.get(node.id)!;
            const state = states[node.id] ?? 'healthy';
            const view = MAP_STATE[state];
            const ago = checkedMinutesAgo?.[node.id];
            return (
              <g
                key={node.id}
                transform={`translate(${p.x - NODE_W / 2} ${p.y - NODE_H / 2})`}
                opacity={near(node.id) ? 1 : 0.3}
                className="dm-node transition-opacity duration-200"
                onPointerEnter={() => setHover(node.id)}
                onPointerLeave={() => setHover(null)}
                data-state={state}
                data-testid={`map-node-${node.id}`}
              >
                {state === 'checking' && <rect x={-4} y={-4} width={NODE_W + 8} height={NODE_H + 8} rx={14} className="dm-scan" />}
                <rect width={NODE_W} height={NODE_H} rx={11} className="dm-card" style={{ stroke: state === 'healthy' ? undefined : view.color }} />
                <circle cx={15} cy={20} r={4} fill={view.color} className={state === 'checking' ? 'dm-blink' : undefined} />
                <text x={26} y={24} className="dm-label">{node.label.length > 16 ? `${node.label.slice(0, 15)}…` : node.label}</text>
                <text x={11} y={42} className="dm-sub">{view.label}{ago !== undefined ? ` · ${ago} min ago` : ''}</text>
                {node.critical && (
                  <g transform={`translate(${NODE_W - 58} -8)`}>
                    <rect width={52} height={15} rx={7.5} className="dm-critical-bg" />
                    <text x={26} y={10.5} textAnchor="middle" className="dm-critical">CRITICAL</text>
                  </g>
                )}
              </g>
            );
          })}
        </svg>
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-white/10 px-5 py-3 text-xs text-white/65">
        {(Object.keys(MAP_STATE) as MapState[]).map(s => <span key={s} className="flex items-center gap-1.5"><span aria-hidden="true" style={{ color: MAP_STATE[s].color }}>{MAP_STATE[s].glyph}</span>{MAP_STATE[s].label}</span>)}
        <span>· CRITICAL = business-critical component{checkedMinutesAgo ? ' · time = since last check' : ''} · hover to trace dependencies</span>
      </div>
      {footnote && <p className="border-t border-white/10 px-5 py-2.5 text-xs text-white/55">{footnote}</p>}
    </figure>
  );
}
