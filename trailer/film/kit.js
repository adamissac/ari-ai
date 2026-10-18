// Ari kit: brand pieces shared by every act. Pure functions of time; build DOM only inside scene build().
// Rebuilt from the real site: frontend/components/ant-colony.tsx (ant drawing, trails), hero.tsx (loop chips),
// story.tsx (story windows, timeline, walkthrough), globals.css (.hero-ink glow + grain).
(() => {
  const C = window.C;
  const { el, reg, put, W, H, clamp, lerp } = C;
  const K = {};
  K.PAD = 140;
  K.col = {
    ink: '#1c1210', ink2: '#2b1d19', paper: '#ffffff', paper2: '#fbf4f2', line: '#ecdcd7', accent: '#c2452d',
    deep: '#8f2f1e', soft: '#f8e7e3', ember: '#e0684a', muted: '#6b5752', faint: '#806b65', ok: '#1f7a4d', okd: '#4fbf87', bad: '#b42318',
  };
  C.fonts = ['700 100px Display', '500 60px Display', '400 40px UI', '500 40px UI', '600 40px UI', '400 30px Mono', '500 30px Mono', '600 30px Mono', '700 80px Wordmark'];

  // ------------------------------------------------------------------ backgrounds
  /** Ink band (frontend .hero-ink): ink, brand glow rising from below, fine film grain. */
  K.ink = (root) => {
    root.style.background = K.col.ink; root.style.color = '#fff';
    const glow = reg(el('div', { class: 'glow' }, root));
    const grain = reg(el('div', { class: 'grain' }, root));
    return { glow, grain };
  };
  /** k: glow strength 0..1, y: glow centre (% of height, >100 sits below the frame), x: centre %. */
  K.inkRun = (t, bg, k = 1, y = 108, x = 50) => {
    const a = (v) => (v * k).toFixed(3);
    put(bg.glow, { css: { background:
      `radial-gradient(75% 65% at ${x}% ${y}%, rgba(194,69,45,${a(1)}) 0%, rgba(194,69,45,${a(0.6)}) 35%, rgba(194,69,45,0) 70%),` +
      `radial-gradient(60% 50% at 85% 0%, rgba(194,69,45,${a(0.3)}) 0%, rgba(194,69,45,0) 70%)` } });
    // grain stays put, like the site's (moving grain is pure noise to a web encoder and bloats the file)
  };
  /** Paper: white or warm paper, with the same grain at low strength so cuts between worlds feel related. */
  K.paper = (root, warm = false) => {
    root.style.background = warm ? K.col.paper2 : K.col.paper; root.style.color = K.col.ink;
    const grain = reg(el('div', { class: 'grain', style: 'opacity:0.05' }, root));
    return { grain };
  };
  K.paperRun = () => {};

  // ------------------------------------------------------------------ type
  /** Mono uppercase eyebrow (frontend .label-mono). Small, so it may slide + fade in. */
  K.eyebrow = (parent, text, x, y, color = 'var(--accent)', size = 26) =>
    reg(el('div', { class: 'abs eyebrow', style: `left:${x}px;top:${y}px;color:${color};font-size:${size}px` }, parent, text), { o: 0 });
  K.eyebrowRun = (t, e, inAt, outAt = null) => {
    const p = C.sp(t, inAt, 'default'), q = outAt == null ? 0 : C.sp(t, outAt, 'snappy');
    put(e, { o: clamp(p * 1.4) * (1 - q), x: -24 * (1 - p) });
  };
  /** A block of UI text (sub line). Rises 30px while fading in (small lines only). */
  K.text = (parent, html, x, y, { size = 36, color = 'inherit', w = 900, weight = 400, cls = 'ui', lh = 1.3 } = {}) =>
    reg(el('div', { class: `abs ${cls}`, style: `left:${x}px;top:${y}px;width:${w}px;font-size:${size}px;line-height:${lh};font-weight:${weight};color:${color};letter-spacing:-0.01em` }, parent, html), { o: 0 });
  K.textRun = (t, e, inAt, outAt = null, dy = 30) => {
    const p = C.sp(t, inAt, 'default'), q = outAt == null ? 0 : C.sp(t, outAt, 'snappy');
    put(e, { o: clamp(p * 1.25) * (1 - q), y: dy * (1 - p) - 40 * q });
  };
  /** Display line built on TYPE.line with the brand's uppercase display. */
  K.head = (parent, text, x, y, size, opts = {}) => TYPE.line(parent, text, { x, y, size, ...opts });
  /** Count-up number for stats. */
  K.count = (t, from, to, b0, b1) => Math.round(lerp(from, to, C.ease.out(C.seg(t, b0, b1))));

  // ------------------------------------------------------------------ story window (frontend .story-window)
  const MARK = { ok: '✓', q: '?', bad: '✕', run: '›', del: '−', add: '+', sp: ' ' };
  const MC = { ok: 'var(--ok)', q: 'var(--accent)', bad: 'var(--bad)', run: 'var(--faint)', del: 'var(--bad)', add: 'var(--ok)', sp: 'var(--faint)' };
  /** White window with a file bar and mono lines that build in one by one. lines: [[kind, text, note], ...] */
  K.win = (parent, { x, y, w, file, lines, size = 28, pad = 26, rowPad = 13 }) => {
    const box = el('div', { class: 'abs', style: `left:${x}px;top:${y}px;width:${w}px;background:#fff;border-radius:16px;overflow:hidden;color:var(--ink);` +
      'box-shadow:0 2px 6px rgba(28,18,16,.08),0 50px 110px -30px rgba(28,18,16,.45)' }, parent);
    el('div', { class: 'mono', style: `display:flex;justify-content:space-between;padding:${pad - 6}px ${pad}px;font-size:${size * 0.78}px;color:var(--faint);border-bottom:1px solid var(--line);background:#fbf4f2` }, box,
      `<span>${file}</span><span style="letter-spacing:.08em">ARI</span>`);
    const rows = lines.map(([kind, text, note]) => {
      const bgc = kind === 'del' ? 'rgba(180,35,24,.07)' : kind === 'add' ? 'rgba(31,122,77,.08)' : 'transparent';
      const r = el('div', { class: 'mono', style: `display:flex;gap:${size * 0.6}px;align-items:baseline;padding:${rowPad}px ${pad}px;font-size:${size}px;white-space:nowrap;background:${bgc}` }, box,
        `<span style="width:${size * 0.7}px;flex:none;color:${MC[kind]};font-weight:600">${MARK[kind]}</span><span style="flex:1;overflow:hidden;text-overflow:ellipsis">${text}</span>` +
        (note ? `<span style="color:${kind === 'bad' ? 'var(--bad)' : 'var(--faint)'};flex:none">${note}</span>` : ''));
      return reg(r, { o: 0 });
    });
    reg(box, { o: 0 });
    return { box, rows, x, y, w };
  };
  /** Window enters as a card rise (scale 0.92 -> 1, opacity snaps in), rows build on their beats. */
  K.winRun = (t, Wd, inAt, rowAt, outAt = null) => {
    const p = C.sp(t, inAt, 'default'), q = outAt == null ? 0 : C.sp(t, outAt, 'default');
    put(Wd.box, { o: p > 0.002 && q < 0.995 ? 1 : 0, y: 80 * (1 - p) - 160 * q, s: 0.94 + 0.06 * p, css: { transformOrigin: '50% 100%' } });
    Wd.rows.forEach((r, i) => {
      const k = C.spHit(t, rowAt[i], 'snappy');
      put(r, { o: k > 0.002 ? 1 : 0, x: -30 * (1 - k) });
    });
  };

  // ------------------------------------------------------------------ chips (frontend hero loop steps)
  K.LOOP = ['Understand', 'Review', 'Attack safely', 'Diagnose', 'Repair', 'Verify', 'Monitor'];
  K.chip = (parent, n, text, size = 28) => {
    const c = el('div', { class: 'abs mono', style: `display:flex;gap:${size * 0.45}px;align-items:center;padding:${size * 0.42}px ${size * 0.75}px;border-radius:${size * 0.35}px;` +
      `background:rgba(255,255,255,.09);color:rgba(255,255,255,.88);font-size:${size}px;font-weight:500;letter-spacing:.04em;text-transform:uppercase;white-space:nowrap` }, parent,
      `<span style="color:rgba(255,255,255,.45)">${String(n).padStart(2, '0')}</span><span>${text}</span>`);
    return reg(c, { o: 0 });
  };

  // ------------------------------------------------------------------ ants (ported from ant-colony.tsx, unchanged geometry)
  K.drawAnt = (ctx, x, y, angle, scale, gait, alpha, color) => {
    if (alpha <= 0.003) return;
    ctx.save(); ctx.translate(x, y); ctx.rotate(angle); ctx.scale(scale, scale);
    ctx.globalAlpha = alpha; ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = 0.9; ctx.lineCap = 'round';
    for (let i = 0; i < 3; i++) {                       // legs: alternating tripods swing in antiphase
      const hx = -1.4 + i * 1.4;
      for (const side of [-1, 1]) {
        const tripod = (i + (side > 0 ? 1 : 0)) % 2 === 0 ? 0 : Math.PI;
        const swing = Math.sin(gait + tripod) * 1.6, base = (i - 1) * 2.6;
        ctx.beginPath(); ctx.moveTo(hx, 0); ctx.lineTo(hx + base * 0.5 + swing * 0.4, side * 3.2); ctx.lineTo(hx + base + swing, side * 5.4); ctx.stroke();
      }
    }
    const flick = Math.sin(gait * 0.5) * 0.6;           // antennae flick with the walk
    for (const side of [-1, 1]) { ctx.beginPath(); ctx.moveTo(4.6, side * 0.7); ctx.quadraticCurveTo(6.8, side * (2.2 + flick), 8.6, side * (3.4 + flick)); ctx.stroke(); }
    ctx.beginPath(); ctx.ellipse(-5.6, 0, 3.9, 2.8, 0, 0, Math.PI * 2); ctx.fill();   // abdomen, petiole, thorax, head
    ctx.beginPath(); ctx.ellipse(-1.9, 0, 0.9, 0.7, 0, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.ellipse(0.4, 0, 2.3, 1.5, 0, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.ellipse(3.7, 0, 1.8, 1.7, 0, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
  };
  K.ANT = 'rgba(255, 238, 228, 0.86)';
  K.SCOUT = 'rgba(255, 150, 120, 0.98)';
  K.TRAILC = 'rgba(224, 104, 74, 0.55)';
  /** Closed curve in normalized coords → polyline with arc length (constant-speed walking). */
  K.trail = (curve, w, h, samples = 900, ox = 0, oy = 0) => {
    const pts = [], cum = [0];
    for (let i = 0; i <= samples; i++) {
      const p = curve((i / samples) * Math.PI * 2); pts.push({ x: ox + p.x * w, y: oy + p.y * h });
      if (i) cum.push(cum[i - 1] + Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y));
    }
    return { pts, cum, length: cum[samples] };
  };
  /** Open polyline path (array of points) with arc length. */
  K.path = (pts) => { const cum = [0]; for (let i = 1; i < pts.length; i++) cum.push(cum[i - 1] + Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y)); return { pts, cum, length: cum[cum.length - 1], open: true }; };
  K.along = (tr, d) => {
    const L = tr.length; const s = tr.open ? clamp(d, 0, L) : ((d % L) + L) % L;
    let lo = 0, hi = tr.cum.length - 1;
    while (hi - lo > 1) { const m = (lo + hi) >> 1; if (tr.cum[m] <= s) lo = m; else hi = m; }
    const a = tr.pts[lo], b = tr.pts[hi], sg = tr.cum[hi] - tr.cum[lo] || 1, k = (s - tr.cum[lo]) / sg, len = Math.hypot(b.x - a.x, b.y - a.y) || 1;
    return { x: a.x + (b.x - a.x) * k, y: a.y + (b.y - a.y) * k, tx: (b.x - a.x) / len, ty: (b.y - a.y) / len };
  };
  /** Stroke the part of a trail between arc distances d0..d1 (wraps on closed trails). */
  K.strokeSpan = (ctx, tr, d0, d1, step = 6) => {
    if (d1 < d0) [d0, d1] = [d1, d0];
    if (d1 - d0 < 0.5) return;
    const n = Math.max(2, Math.ceil((d1 - d0) / step));
    ctx.beginPath();
    for (let i = 0; i <= n; i++) { const p = K.along(tr, d0 + ((d1 - d0) * i) / n); i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y); }
    ctx.stroke();
  };
  /** One walking ant on a trail at distance d (dir ±1), with lane offset + wobble, like the site. */
  K.antOn = (ctx, tr, d, dir, { t = 0, lane = 0, seed = 0.5, phase = 0, scale = 1.1, alpha = 1, color = K.ANT } = {}) => {
    const p = K.along(tr, d), hx = p.tx * dir, hy = p.ty * dir;
    const wob = Math.sin(t * (1.3 + seed) * 2 + phase) * 2.2 * scale, off = lane + wob;
    const angle = Math.atan2(hy, hx) + Math.cos(t * (1.3 + seed) * 2 + phase) * 0.12;
    K.drawAnt(ctx, p.x - hy * off, p.y + hx * off, angle, scale, d * 0.42 / scale + phase, alpha, color);
  };

  /**
   * The colony as a pure function of time (the site's colony is a stateful simulation; this keeps its look:
   * nests, a first wave already out, followers at a quickening pace, pheromone dashes laid where ants have walked).
   * spec: { trails: [tr...], nests: [{trail, at}], n, t0 (seconds when the colony starts), seed, speed }
   */
  K.colony = (spec) => {
    const r = C.mulberry32(spec.seed || 7), ants = [];
    const nests = spec.nests, max = spec.n || 30;
    let tSpawn = 0;
    for (let i = 0; i < max; i++) {
      const first = i < (spec.first ?? 8);
      const ni = i % nests.length, nest = nests[ni], tr = spec.trails[nest.trail];
      const scout = i < nests.length;
      const dir = scout || r() < 0.7 ? (ni % 2 === 0 ? 1 : -1) : (ni % 2 === 0 ? -1 : 1);
      const start = first && !scout ? r() * tr.length : nest.at * tr.length;
      if (!first) tSpawn += 0.18 + 0.9 * (1 - Math.min(1, i / (max * 0.6))) * r();
      ants.push({ trail: nest.trail, start, dir, speed: (scout ? 150 : 120 + r() * 80) * (spec.speed || 1), lane: scout ? 0 : (r() - 0.5) * 16,
        seed: r(), phase: r() * Math.PI * 2, born: first ? (scout ? 0 : -0.15 * (i - nests.length)) : tSpawn, scout });
    }
    return { spec, ants };
  };
  /** Draw the colony at time tc (seconds since the colony started). k fades everything (scene exits). */
  K.colonyDraw = (ctx, col, tc, { k = 1, scale = 1.25, dash = true, nestGlow = true, alpha = 1 } = {}) => {
    const { spec, ants } = col;
    if (dash) {
      ctx.save(); ctx.lineWidth = 1.6; ctx.setLineDash([2, 9]); ctx.lineDashOffset = -tc * 22; ctx.strokeStyle = K.TRAILC; ctx.globalAlpha = k * alpha;
      for (const a of ants) {
        const age = tc - a.born; if (age <= 0) continue;
        const tr = spec.trails[a.trail], d = a.speed * age;
        if (d >= tr.length) K.strokeSpan(ctx, tr, 0, tr.length); else K.strokeSpan(ctx, tr, a.start, a.start + a.dir * d);
      }
      ctx.restore();
    }
    if (nestGlow) for (const n of spec.nests) {
      const p = K.along(spec.trails[n.trail], n.at * spec.trails[n.trail].length);
      const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, 34);
      g.addColorStop(0, `rgba(214, 92, 64, ${0.38 * k})`); g.addColorStop(1, 'rgba(214, 92, 64, 0)');
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(p.x, p.y, 34, 0, Math.PI * 2); ctx.fill();
    }
    for (const a of ants) {
      const age = tc - a.born; if (age <= -0.8) continue;
      const tr = spec.trails[a.trail], d = a.start + a.dir * a.speed * Math.max(0, age);
      K.antOn(ctx, tr, d, a.dir, { t: tc, lane: a.lane, seed: a.seed, phase: a.phase, scale, alpha: clamp((age + 0.8) / 0.8) * k * alpha, color: a.scout ? K.SCOUT : K.ANT });
    }
  };
  // The site's two trails (normalized to the hero band): a figure-eight and a wobbly ring.
  K.TRAILS = [
    (t) => ({ x: 0.5 + 0.42 * Math.cos(t), y: 0.56 + 0.3 * Math.sin(2 * t) }),
    (t) => { const r = 0.82 + 0.18 * Math.cos(3 * t); return { x: 0.5 + 0.45 * r * Math.cos(t), y: 0.5 - 0.38 * r * Math.sin(t) }; },
  ];
  K.NESTS = [{ trail: 0, at: 0 }, { trail: 0, at: 0.5 }, { trail: 1, at: 0.25 }, { trail: 1, at: 0.75 }];

  // ------------------------------------------------------------------ ant mark (logo) and real UI screenshots
  K.mark = (parent, h, color = '#fff') => reg(el('div', { class: 'abs mark', style: `width:${Math.round(h * 1.41)}px;height:${h}px;color:${color}` }, parent), { o: 0 });
  /** A captured screen (2x JPEG/PNG of a 1920x1080 page) inside a rounded window; img is laid out in page px. */
  K.screen = (parent, srcs, { x, y, w, h, radius = 16 } = {}) => {
    const box = el('div', { class: 'shot', style: `left:${x}px;top:${y}px;width:${w}px;height:${h}px;border-radius:${radius}px` }, parent);
    const cam = el('div', { class: 'abs', style: 'width:1920px;height:1080px' }, box);
    const imgs = srcs.map((s) => reg(el('img', { src: `../assets/cap/${s}`, style: 'width:1920px;height:auto' }, cam), { o: 0 }));
    reg(box, { o: 0 }); reg(cam);
    return { box, cam, imgs, w, h };
  };
  /** Show image i of a screen and aim its camera: page point (px, py) lands at the window centre, zoom z. */
  K.screenRun = (S, i, px, py, z) => {
    S.imgs.forEach((im, k) => put(im, { o: k === i ? 1 : 0 }));
    put(S.cam, { x: S.w / 2 - px * z, y: S.h / 2 - py * z, s: z });
  };
  /** Camera framing: page point (px, py) to stage point (cx, cy) at zoom s, as put() props on a full-frame wrapper. */
  K.aim = (px, py, s, cx = W / 2, cy = H / 2) => ({ x: cx - px * s, y: cy - py * s, s });

  // ------------------------------------------------------------------ transition: the ant pulls the next scene across
  /** Progress of a left→right wipe between beats (ease in-out). Use the same numbers in the overlay ant. */
  K.wipe = (t, b0, b1) => C.ease.inOut(C.seg(t, b0, b1));

  window.K = K;
})();
