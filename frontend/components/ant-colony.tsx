'use client';

import { useEffect, useRef } from 'react';

/**
 * Landing-hero ant colony (decorative canvas). One scout leaves the nest and lays a pheromone
 * trail; more ants follow at a quickening pace until the colony reaches a modest size, and a
 * second trail opens halfway. Ants walk with a tripod gait and step around the pointer.
 * Pauses off screen and in background tabs; reduced motion gets one static frame.
 */

type Pt = { x: number; y: number };

/** A closed trail in normalized (0..1) coordinates, sampled at t ∈ [0, 2π). */
export type Curve = (t: number) => Pt;

export const TRAILS: readonly Curve[] = [
  // Figure-eight across the hero; t=0 is the nest on the right edge.
  t => ({ x: 0.5 + 0.42 * Math.cos(t), y: 0.56 + 0.3 * Math.sin(2 * t) }),
  // Wobbly ring that starts beside the nest and circles the headline.
  t => {
    const r = 0.82 + 0.18 * Math.cos(3 * t);
    return { x: 0.5 + 0.45 * r * Math.cos(t), y: 0.5 - 0.38 * r * Math.sin(t) };
  },
];

export interface Trail { pts: Pt[]; cum: number[]; length: number }

/** Polyline of the curve in pixels with cumulative arc length, for constant-speed walking. */
export function buildTrail(curve: Curve, w: number, h: number, samples = 900): Trail {
  const pts: Pt[] = [];
  const cum: number[] = [0];
  for (let i = 0; i <= samples; i++) {
    const p = curve((i / samples) * Math.PI * 2);
    pts.push({ x: p.x * w, y: p.y * h });
    if (i > 0) cum.push(cum[i - 1]! + Math.hypot(pts[i]!.x - pts[i - 1]!.x, pts[i]!.y - pts[i - 1]!.y));
  }
  return { pts, cum, length: cum[samples]! };
}

/** Point and unit tangent at arc distance `d` (wraps around the closed trail). */
export function along(trail: Trail, d: number): { p: Pt; tx: number; ty: number } {
  const L = trail.length;
  const s = ((d % L) + L) % L;
  let lo = 0;
  let hi = trail.cum.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (trail.cum[mid]! <= s) lo = mid;
    else hi = mid;
  }
  const a = trail.pts[lo]!;
  const b = trail.pts[hi]!;
  const seg = trail.cum[hi]! - trail.cum[lo]! || 1;
  const k = (s - trail.cum[lo]!) / seg;
  const len = Math.hypot(b.x - a.x, b.y - a.y) || 1;
  return { p: { x: a.x + (b.x - a.x) * k, y: a.y + (b.y - a.y) * k }, tx: (b.x - a.x) / len, ty: (b.y - a.y) / len };
}

/** Colony size for a canvas area: "more and more, not too much". */
export const colonySize = (w: number, h: number): number => Math.max(10, Math.min(34, Math.round((w * h) / 36000)));

/** Seconds until the next ant, given how many are out: slow at first, then quicker. */
export const spawnGap = (count: number, max: number): number => 2.2 - 1.75 * Math.min(1, count / Math.max(1, max * 0.6));

interface Ant { trail: number; d: number; speed: number; dir: 1 | -1; lane: number; push: number; phase: number; seed: number; age: number; scout: boolean }

const ANT = 'rgba(255, 238, 228, 0.82)';
const SCOUT = 'rgba(255, 150, 120, 0.95)';

function drawAnt(ctx: CanvasRenderingContext2D, x: number, y: number, angle: number, scale: number, gait: number, alpha: number, scout: boolean) {
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(angle);
  ctx.scale(scale, scale);
  ctx.globalAlpha = alpha;
  const color = scout ? SCOUT : ANT;
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = 0.9;
  ctx.lineCap = 'round';
  // Legs: alternating tripods swing in antiphase.
  for (let i = 0; i < 3; i++) {
    const hx = -1.4 + i * 1.4;
    for (const side of [-1, 1]) {
      const tripod = (i + (side > 0 ? 1 : 0)) % 2 === 0 ? 0 : Math.PI;
      const swing = Math.sin(gait + tripod) * 1.6;
      const base = (i - 1) * 2.6;
      ctx.beginPath();
      ctx.moveTo(hx, 0);
      ctx.lineTo(hx + base * 0.5 + swing * 0.4, side * 3.2);
      ctx.lineTo(hx + base + swing, side * 5.4);
      ctx.stroke();
    }
  }
  // Antennae flick with the walk.
  const flick = Math.sin(gait * 0.5) * 0.6;
  for (const side of [-1, 1]) {
    ctx.beginPath();
    ctx.moveTo(4.6, side * 0.7);
    ctx.quadraticCurveTo(6.8, side * (2.2 + flick), 8.6, side * (3.4 + flick));
    ctx.stroke();
  }
  // Body: abdomen, petiole, thorax, head.
  ctx.beginPath(); ctx.ellipse(-5.6, 0, 3.9, 2.8, 0, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath(); ctx.ellipse(-1.9, 0, 0.9, 0.7, 0, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath(); ctx.ellipse(0.4, 0, 2.3, 1.5, 0, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath(); ctx.ellipse(3.7, 0, 1.8, 1.7, 0, 0, Math.PI * 2); ctx.fill();
  ctx.restore();
}

export function AntColony({ play = true }: { play?: boolean }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx || !play) return;
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const host = canvas.parentElement ?? canvas;

    let w = 0;
    let h = 0;
    let trails: Trail[] = [];
    let max = 0;
    let scale = 1;
    const resize = () => {
      const box = canvas.getBoundingClientRect();
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      w = Math.max(1, box.width);
      h = Math.max(1, box.height);
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      trails = TRAILS.map(c => buildTrail(c, w, h));
      max = colonySize(w, h);
      scale = w < 640 ? 0.85 : 1.1;
    };
    resize();

    const ants: Ant[] = [];
    const revealed = [0, 0]; // pheromone laid so far on each trail (px)
    const open = [true, false];
    let clock = 0;
    let nextSpawn = 0;
    let pointer: Pt | null = null;

    const spawn = (trail: number, scout: boolean) => {
      const seed = Math.random();
      ants.push({
        trail,
        d: 0,
        speed: scout ? 52 : 46 + seed * 26,
        dir: trail === 1 && !scout && seed > 0.55 ? -1 : 1,
        lane: scout ? 0 : (Math.random() - 0.5) * 12,
        push: 0,
        phase: Math.random() * Math.PI * 2,
        seed,
        age: 0,
        scout,
      });
    };

    const drawTrails = (t: number) => {
      ctx.save();
      ctx.lineWidth = 1.2;
      ctx.setLineDash([1.5, 7]);
      ctx.lineDashOffset = -t * 18;
      trails.forEach((trail, i) => {
        if (!open[i] || revealed[i]! <= 0) return;
        ctx.strokeStyle = 'rgba(224, 104, 74, 0.5)';
        ctx.beginPath();
        const limit = Math.min(trail.length, revealed[i]!);
        ctx.moveTo(trail.pts[0]!.x, trail.pts[0]!.y);
        for (let k = 1; k < trail.pts.length && trail.cum[k]! <= limit; k++) ctx.lineTo(trail.pts[k]!.x, trail.pts[k]!.y);
        ctx.stroke();
      });
      ctx.restore();
      // The nest: a soft ember ring at the trail start.
      const nest = trails[0]?.pts[0];
      if (nest) {
        const g = ctx.createRadialGradient(nest.x, nest.y, 0, nest.x, nest.y, 26);
        g.addColorStop(0, 'rgba(214, 92, 64, 0.35)');
        g.addColorStop(1, 'rgba(214, 92, 64, 0)');
        ctx.fillStyle = g;
        ctx.beginPath(); ctx.arc(nest.x, nest.y, 26, 0, Math.PI * 2); ctx.fill();
      }
    };

    const drawAnts = () => {
      for (const a of ants) {
        const trail = trails[a.trail];
        if (!trail) continue;
        const { p, tx, ty } = along(trail, a.d * a.dir);
        const hx = tx * a.dir;
        const hy = ty * a.dir;
        const wobble = Math.sin(clock * (1.3 + a.seed) + a.phase) * 2.2;
        const off = a.lane + wobble + a.push;
        const x = p.x - hy * off;
        const y = p.y + hx * off;
        const angle = Math.atan2(hy, hx) + Math.cos(clock * (1.3 + a.seed) + a.phase) * 0.12;
        drawAnt(ctx, x, y, angle, scale, a.d * 0.42 + a.phase, Math.min(1, a.age / 0.8), a.scout);
      }
    };

    if (reduced) {
      // One calm frame: both trails laid, a small colony in place.
      revealed[0] = trails[0]!.length; revealed[1] = trails[1]!.length; open[1] = true;
      for (let i = 0; i < 12; i++) {
        spawn(i % 2, false);
        const a = ants[ants.length - 1]!;
        a.d = (i / 12) * trails[a.trail]!.length; a.age = 1;
      }
      drawTrails(0);
      drawAnts();
      return;
    }

    let raf = 0;
    let last = 0;
    let visible = true;
    const frame = (now: number) => {
      raf = 0;
      const dt = last ? Math.min(0.05, (now - last) / 1000) : 0;
      last = now;
      clock += dt;

      // Grow the colony: one scout first, then followers at a quickening pace.
      if (ants.length === 0) spawn(0, true);
      else if (ants.length < max && clock >= nextSpawn && revealed[0]! > trails[0]!.length * 0.25) {
        const second = open[1] && ants.length % 3 === 0;
        spawn(second ? 1 : 0, false);
        nextSpawn = clock + spawnGap(ants.length, max);
      }
      if (!open[1] && ants.length >= Math.ceil(max / 2)) { open[1] = true; spawn(1, true); }

      for (const a of ants) {
        a.age += dt;
        a.d += a.speed * dt;
        if (a.scout) revealed[a.trail] = Math.max(revealed[a.trail]!, a.d);
        // Step around the pointer: push sideways, then drift back to the lane.
        let target = 0;
        const trail = trails[a.trail];
        if (pointer && trail) {
          const { p, tx, ty } = along(trail, a.d * a.dir);
          const dx = p.x - pointer.x;
          const dy = p.y - pointer.y;
          const dist = Math.hypot(dx, dy);
          if (dist < 110) {
            const side = Math.sign(-ty * a.dir * dx + tx * a.dir * dy) || 1;
            target = side * (110 - dist) * 0.55;
          }
        }
        a.push += (target - a.push) * Math.min(1, dt * 6);
      }

      ctx.clearRect(0, 0, w, h);
      drawTrails(clock);
      drawAnts();
      if (visible && !document.hidden) raf = requestAnimationFrame(frame);
    };
    const start = () => { if (!raf && visible && !document.hidden) { last = 0; raf = requestAnimationFrame(frame); } };

    const io = new IntersectionObserver(([entry]) => { visible = Boolean(entry?.isIntersecting); start(); });
    io.observe(canvas);
    const onVis = () => start();
    const onMove = (e: PointerEvent) => { const b = canvas.getBoundingClientRect(); pointer = { x: e.clientX - b.left, y: e.clientY - b.top }; };
    const onLeave = () => { pointer = null; };
    const onResize = () => resize();
    document.addEventListener('visibilitychange', onVis);
    host.addEventListener('pointermove', onMove);
    host.addEventListener('pointerleave', onLeave);
    window.addEventListener('resize', onResize);
    start();
    return () => {
      cancelAnimationFrame(raf);
      io.disconnect();
      document.removeEventListener('visibilitychange', onVis);
      host.removeEventListener('pointermove', onMove);
      host.removeEventListener('pointerleave', onLeave);
      window.removeEventListener('resize', onResize);
    };
  }, [play]);

  return <canvas ref={ref} aria-hidden="true" data-testid="ant-colony" className="hero-colony" />;
}
