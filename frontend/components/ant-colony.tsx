'use client';

import { useEffect, useRef } from 'react';

/**
 * Landing-hero ant colony (decorative canvas). A first wave of ants comes out of several nests
 * around the hero (and a few are already out foraging), laying pheromone trails as they walk;
 * more follow at a quickening pace until the colony reaches a modest size. Ants walk with a tripod gait and step around the pointer.
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

/** Where ants come out: a trail and a fraction of its length. Right, left, top and bottom. */
export const NESTS: readonly { trail: number; at: number }[] = [
  { trail: 0, at: 0 },
  { trail: 0, at: 0.5 },
  { trail: 1, at: 0.25 },
  { trail: 1, at: 0.75 },
];

/** Ants already out when the hero opens: a handful, never the whole colony. */
export const firstWave = (max: number): number => Math.max(NESTS.length + 1, Math.min(10, Math.round(max * 0.3)));

const BIN = 8; // pheromone resolution along a trail, px

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

/** Colony size for a canvas area: a lighter decorative population. */
export const colonySize = (w: number, h: number): number => Math.max(6, Math.min(16, Math.round((w * h) / 80000)));

/** Seconds until the next ant, given how many are out: slow at first, then quicker. */
export const spawnGap = (count: number, max: number): number => 2.2 - 1.75 * Math.min(1, count / Math.max(1, max * 0.6));

interface Ant { trail: number; start: number; d: number; speed: number; dir: 1 | -1; lane: number; push: number; phase: number; seed: number; age: number; scout: boolean }

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
    // Pheromone laid on each trail, in BIN-px bins, with the bin centre points cached per size.
    let laid: Uint8Array[] = [];
    let binPts: Pt[][] = [];
    const layout = () => {
      laid = trails.map(t => new Uint8Array(Math.ceil(t.length / BIN)));
      binPts = trails.map((t, i) => Array.from(laid[i]!, (_, k) => along(t, (k + 0.5) * BIN).p));
    };
    layout();
    let clock = 0;
    let nextSpawn = 0;
    let pointer: Pt | null = null;

    const spawn = (trail: number, start: number, dir: 1 | -1, scout: boolean) => {
      const seed = Math.random();
      ants.push({
        trail,
        start,
        d: 0,
        speed: scout ? 52 : 44 + seed * 28,
        dir,
        lane: scout ? 0 : (Math.random() - 0.5) * 12,
        push: 0,
        phase: Math.random() * Math.PI * 2,
        seed,
        age: 0,
        scout,
      });
    };
    const nestAt = (i: number) => NESTS[i]!.at * (trails[NESTS[i]!.trail]?.length ?? 0);
    const fromNest = (i: number, scout: boolean) => {
      const nestDir: 1 | -1 = i % 2 === 0 ? 1 : -1;
      const dir: 1 | -1 = scout || Math.random() < 0.7 ? nestDir : nestDir === 1 ? -1 : 1;
      spawn(NESTS[i]!.trail, nestAt(i), dir, scout);
    };
    const firstOut = () => {
      NESTS.forEach((_, i) => fromNest(i, true));
      // The rest of the first wave is already out foraging somewhere along the trails.
      for (let n = NESTS.length; n < firstWave(max); n++) {
        const trail = n % trails.length;
        spawn(trail, Math.random() * trails[trail]!.length, Math.random() < 0.5 ? 1 : -1, false);
        ants[ants.length - 1]!.age = -0.25 * (n - NESTS.length); // staggered fade-in
      }
    };

    const drawTrails = (t: number) => {
      ctx.save();
      ctx.lineWidth = 1.2;
      ctx.setLineDash([1.5, 7]);
      ctx.lineDashOffset = -t * 18;
      ctx.strokeStyle = 'rgba(224, 104, 74, 0.5)';
      ctx.beginPath();
      laid.forEach((bins, i) => {
        const pts = binPts[i]!;
        for (let k = 0; k < bins.length; k++) {
          if (!bins[k]) continue;
          if (k === 0 || !bins[k - 1]) ctx.moveTo(pts[k]!.x, pts[k]!.y);
          else ctx.lineTo(pts[k]!.x, pts[k]!.y);
        }
        if (bins[0] && bins[bins.length - 1]) ctx.lineTo(pts[0]!.x, pts[0]!.y); // close the loop
      });
      ctx.stroke();
      ctx.restore();
      // The nests: soft ember glows where the ants come out.
      NESTS.forEach((_, i) => {
        const trail = trails[NESTS[i]!.trail];
        if (!trail) return;
        const { p } = along(trail, nestAt(i));
        const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, 24);
        g.addColorStop(0, 'rgba(214, 92, 64, 0.35)');
        g.addColorStop(1, 'rgba(214, 92, 64, 0)');
        ctx.fillStyle = g;
        ctx.beginPath(); ctx.arc(p.x, p.y, 24, 0, Math.PI * 2); ctx.fill();
      });
    };

    const pos = (a: Ant) => a.start + a.d * a.dir;

    const drawAnts = () => {
      for (const a of ants) {
        const trail = trails[a.trail];
        if (!trail) continue;
        const { p, tx, ty } = along(trail, pos(a));
        const hx = tx * a.dir;
        const hy = ty * a.dir;
        const wobble = Math.sin(clock * (1.3 + a.seed) + a.phase) * 2.2;
        const off = a.lane + wobble + a.push;
        const x = p.x - hy * off;
        const y = p.y + hx * off;
        const angle = Math.atan2(hy, hx) + Math.cos(clock * (1.3 + a.seed) + a.phase) * 0.12;
        drawAnt(ctx, x, y, angle, scale, a.d * 0.42 + a.phase, Math.max(0, Math.min(1, a.age / 0.8)), a.scout);
      }
    };

    if (reduced) {
      // One calm frame: trails laid, a small colony spread around them.
      laid.forEach(bins => bins.fill(1));
      for (let i = 0; i < 12; i++) {
        const trail = i % trails.length;
        spawn(trail, (i / 12) * trails[trail]!.length, i % 3 === 0 ? -1 : 1, false);
        ants[ants.length - 1]!.age = 1;
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

      // Grow the colony: a first wave from every nest, then followers at a quickening pace.
      if (ants.length === 0) { firstOut(); nextSpawn = clock + spawnGap(ants.length, max); }
      else if (ants.length < max && clock >= nextSpawn) {
        fromNest(Math.floor(Math.random() * NESTS.length), false);
        nextSpawn = clock + spawnGap(ants.length, max);
      }

      for (const a of ants) {
        a.age += dt;
        a.d += a.speed * dt;
        const bins = laid[a.trail];
        const L = trails[a.trail]?.length ?? 1;
        if (bins && a.age > 0) bins[Math.min(bins.length - 1, Math.floor((((pos(a) % L) + L) % L) / BIN))] = 1;
        // Step around the pointer: push sideways, then drift back to the lane.
        let target = 0;
        const trail = trails[a.trail];
        if (pointer && trail) {
          const { p, tx, ty } = along(trail, pos(a));
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
    const onResize = () => {
      const before = trails.map(t => t.length);
      const oldLaid = laid;
      resize();
      layout();
      // Keep each ant and the laid pheromone at the same place along its trail.
      laid.forEach((bins, i) => { const old = oldLaid[i]; if (old) for (let k = 0; k < bins.length; k++) bins[k] = old[Math.floor((k / bins.length) * old.length)] ?? 0; });
      for (const a of ants) { const k = (trails[a.trail]?.length ?? 1) / (before[a.trail] || 1); a.start *= k; a.d *= k; }
    };
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
