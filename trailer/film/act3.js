// ACT 3: how it works. The seven-step loop, then each part on the real refund finding: understand intent,
// test like an attacker, seven agents, one finding start to proof, the repair and its verification, monitoring.
// Copy is the site's own (frontend/components/story.tsx, hero.tsx) and the demo run (frontend/lib/demo/scenarios.ts).
(() => {
  const { W, H, el, reg, put, scene, canvas, sp, spHit, trk, seg, clamp, lerp, ease, bt, beatOf, rectOf } = C;
  const { rise } = TYPE;
  const PAD = K.PAD;
  const full = (root) => reg(el('div', { class: 'abs', style: `width:${W}px;height:${H}px` }, root));

  // ------------------------------------------------------------------ 6 · loop: assurance that runs on every change (b48 → b56)
  scene({
    name: 'loop', from: 'loop', to: 'understand',
    build(root, S) {
      S.bg = K.ink(root);
      S.cam = full(root);
      S.eye = K.eyebrow(S.cam, 'How it works', PAD, 200, 'rgba(255,255,255,.6)');
      S.t1 = K.head(S.cam, 'ASSURANCE THAT RUNS', PAD, 262, 112, { color: '#fff' });
      S.t2 = K.head(S.cam, 'ON EVERY CHANGE.', PAD, 382, 112, { color: 'var(--ember)' });
      S.row = el('div', { class: 'abs', style: `left:${PAD}px;top:640px;display:flex;gap:12px` }, S.cam);
      S.chips = K.LOOP.map((s, i) => { const c = K.chip(S.row, i + 1, s, 25); c.style.position = 'relative'; c.style.transformOrigin = '50% 50%'; return c; });
      S.grow = reg(el('div', { class: 'abs', style: `width:${W}px;height:${H}px;background:var(--accent)` }, root), { o: 0 });
    },
    run(t, b, S) {
      K.inkRun(t, S.bg, 0.35, 118);
      put(S.cam, K.aim(W / 2, H / 2, 1 + 0.04 * ease.inOut(seg(t, 48, 55))));
      K.eyebrowRun(t, S.eye, 47.9);
      rise(t, S.t1, [48, 48.25, 48.5], 54.6, { exit: 0.3 });
      rise(t, S.t2, [49, 49.25, 49.5], 54.6, { exit: 0.3 });
      // the pipeline runs: one chip lights per quarter beat, then it comes back to Understand
      const step = b < 52.5 ? -1 : b < 54.25 ? Math.floor((b - 52.5) / 0.25) : 0;
      S.chips.forEach((c, i) => {
        const p = spHit(t, 50.5 + i * 0.25, 'snappy');
        const on = i === step && b < 54.25 ? 1 : 0, home = i === 0 ? spHit(t, 54.5, 'snappy') : 0;
        const lit = Math.max(on, home);
        put(c, { o: p > 0.002 ? 1 : 0, s: 0.85 + 0.15 * p, y: 30 * (1 - p), css: { background: lit > 0.5 ? 'var(--accent)' : 'rgba(255,255,255,.09)', color: lit > 0.5 ? '#fff' : 'rgba(255,255,255,.88)' } });
      });
    },
    after(t, b, S) {
      // push-through: the lit Understand chip grows until its red fills the frame (exact start rect from live layout)
      const g = ease.expoIn(seg(t, 54.85, 55.9));
      if (g <= 0.001) { put(S.grow, { o: 0 }); return; }
      const r = rectOf(S.chips[0]), k = (v) => lerp(v, -2, g).toFixed(2);
      put(S.grow, { o: 1, clip: `inset(${k(r.y)}px ${k(W - r.x - r.w)}px ${k(H - r.y - r.h)}px ${k(r.x)}px round ${(9 * (1 - g)).toFixed(1)}px)` });
    },
  });

  // ------------------------------------------------------------------ 7 · understand: learn what it should do (b56 → b64)
  const NODES = (() => {                                             // a small, seeded code-intelligence graph
    const r = C.mulberry32(56), n = [];
    const named = [['app.py', 0.18, 0.2], ['create_refund', 0.42, 0.34], ['store.py', 0.72, 0.18], ['refunds_for', 0.85, 0.42], ['require_owner', 0.2, 0.58], ['README §Refunds', 0.55, 0.62], ['test_api.py', 0.82, 0.78], ['docstring', 0.3, 0.86]];
    for (const [label, x, y] of named) n.push({ label, x, y });
    for (let i = 0; i < 22; i++) n.push({ label: '', x: 0.05 + r() * 0.9, y: 0.06 + r() * 0.88 });
    const e = [];
    n.forEach((a, i) => { const d = n.map((bb, j) => [Math.hypot(a.x - bb.x, a.y - bb.y), j]).sort((p, q) => p[0] - q[0]); for (const [, j] of d.slice(1, 3)) if (i < j) e.push([i, j]); });
    return { n, e };
  })();
  const GX = 1000, GY = 170, GW = 780, GH = 700;
  scene({
    name: 'understand', from: 'understand', to: 'attack', post: 0.5,
    build(root, S) {
      S.bg = K.paper(root);
      S.cam = full(root);
      S.ctx = canvas(S.cam);
      S.eye = K.eyebrow(S.cam, '01 · Understand intent', PAD, 200);
      S.t1 = K.head(S.cam, 'LEARN WHAT IT', PAD, 262, 112, { color: 'var(--ink)' });
      S.t2 = K.head(S.cam, 'SHOULD DO.', PAD, 382, 112, { color: 'var(--accent)' });
      S.body = K.text(S.cam, 'Code intelligence indexes the repository and extracts expectations from specs, docs, tests and history.', PAD, 560, { size: 34, color: 'var(--muted)', w: 760 });
      S.win = K.win(S.cam, { x: GX, y: 520, w: 800, file: 'expectations', size: 25, lines: [
        ['ok', 'refund ≤ captured amount', 'confirmed · docstring'], ['ok', 'discounts round half-up', 'confirmed · test'], ['q', 'owner check on /refunds', 'inferred']] });
      // the expectation the commit breaks: its note flips to the violation (the flaw from act 1)
      S.mk = reg(S.win.rows[0].firstChild); S.note = reg(S.win.rows[0].lastChild);
      S.cover = reg(el('div', { class: 'abs', style: `width:${W}px;height:${H}px;background:var(--accent)` }, root));
    },
    run(t, b, S) {
      K.paperRun(t, S.bg);
      put(S.cover, { clip: C.inset(0, 0, 100 * ease.inOut(seg(t, 56, 57)), 0) });   // the red lifts off the page
      put(S.cam, K.aim(W / 2, H / 2, 1.04 - 0.04 * ease.out(seg(t, 56, 60))));
      const out = ease.inOut(seg(t, 63.5, 64));                                      // whip to the attack scene
      put(S.root, { x: -W * out });
      K.eyebrowRun(t, S.eye, 56.5);
      rise(t, S.t1, [57, 57.25, 57.5]);
      rise(t, S.t2, [57.75, 58]);
      K.textRun(t, S.body, 58.5);
      K.winRun(t, S.win, 57.5, ['u1', 'u2', 'u3']);
      const f = spHit(t, 61.5, 'snappy');
      if (f > 0.5) {
        put(S.mk, { html: '✕', css: { color: 'var(--bad)' } });
        put(S.note, { html: 'broken by 06e0663', css: { color: 'var(--bad)', fontWeight: '600' } });
        put(S.win.rows[0], { o: 1, css: { background: 'rgba(180,35,24,.08)' } });
      }
      // graph: nodes fade up as the index scan passes, named nodes get labels, edges draw behind
      const g = S.ctx; g.clearRect(0, 0, W, H);
      const scan = seg(t, 56.4, 58.6);
      g.save(); g.lineWidth = 1.5;
      for (const [i, j] of NODES.e) {
        const a = NODES.n[i], c = NODES.n[j], k = clamp((scan * 1.15 - Math.max(a.x, c.x)) * 6);
        if (k <= 0) continue;
        g.strokeStyle = `rgba(28,18,16,${(0.14 * k).toFixed(3)})`; g.beginPath();
        g.moveTo(GX + a.x * GW, GY + a.y * GH); g.lineTo(GX + lerp(a.x, c.x, k) * GW, GY + lerp(a.y, c.y, k) * GH); g.stroke();
      }
      g.font = '500 22px Mono'; g.textBaseline = 'middle';
      NODES.n.forEach((nd, i) => {
        const k = clamp((scan * 1.15 - nd.x) * 8); if (k <= 0) return;
        const x = GX + nd.x * GW, y = GY + nd.y * GH, hot = nd.label === 'create_refund' || nd.label === 'docstring' || nd.label === 'README §Refunds';
        g.fillStyle = hot ? `rgba(194,69,45,${k})` : `rgba(28,18,16,${(0.55 * k).toFixed(3)})`;
        g.beginPath(); g.arc(x, y, (nd.label ? 7 : 4.5) * (0.6 + 0.4 * k), 0, Math.PI * 2); g.fill();
        if (nd.label) { g.fillStyle = hot ? `rgba(194,69,45,${k})` : `rgba(107,87,82,${k})`; g.fillText(nd.label, x + 14, y); }
      });
      g.restore();
      put(S.ctx.canvas, { o: 1 - 0.75 * sp(t, 57.5, 'default') });
    },
  });

  // ------------------------------------------------------------------ 8 · attack: test it like an attacker (b64 → b72)
  scene({
    name: 'attack', from: 'attack', to: 'agents', pre: 0.5,
    build(root, S) {
      S.bg = K.ink(root);
      S.cam = full(root);
      S.eye = K.eyebrow(S.cam, '02 · Review and attack', PAD, 200, 'var(--ember)');
      S.t1 = K.head(S.cam, 'TEST IT LIKE', PAD, 262, 112, { color: '#fff' });
      S.t2 = K.head(S.cam, 'AN ATTACKER.', PAD, 382, 112, { color: 'var(--ember)' });
      S.body = K.text(S.cam, 'The Reviewer writes tests that reproduce defects, and seven security agents probe inside an approved sandbox scope.', PAD, 560, { size: 34, color: 'rgba(255,255,255,.74)', w: 760 });
      S.win = K.win(S.cam, { x: 980, y: 330, w: 800, file: 'sandbox · pytest', size: 26, lines: [
        ['run', 'generated/test_refunds.py', ''], ['bad', 'test_refunds_cannot_exceed_payment_in_total', ''], ['bad', 'reproduced on head', '2 / 2'], ['bad', 'POST /refunds 60.00 + 60.00', '201, 201']] });
      S.scope = reg(el('div', { class: 'abs', style: 'left:946px;top:296px;width:868px;height:420px;border:3px dashed rgba(224,104,74,.85);border-radius:30px' }, S.cam), { o: 0 });
      S.scopeL = reg(el('div', { class: 'abs eyebrow', style: 'left:976px;top:740px;color:var(--ember);font-size:24px' }, S.cam, 'Approved sandbox scope · nothing leaves it'), { o: 0 });
    },
    run(t, b, S) {
      K.inkRun(t, S.bg, 0.5, 112, 70);
      put(S.root, { x: W * (1 - ease.inOut(seg(t, 63.5, 64))) });
      put(S.cam, K.aim(W / 2, H / 2, 1 + 0.05 * ease.inOut(seg(t, 64, 72))));
      K.eyebrowRun(t, S.eye, 63.4);
      rise(t, S.t1, [63.5, 63.65, 63.8], 71.3, { exit: 0.3 });
      rise(t, S.t2, [64, 64.25], 71.3, { exit: 0.3 });
      K.textRun(t, S.body, 66, 71.2);
      K.winRun(t, S.win, 64.25, ['a1', 'a2', 'a3', 68], 71.3);
      const sc = ease.inOut(seg(t, 68.75, 69.75)), gone = sp(t, 71.3, 'default');
      put(S.scope, { o: sc > 0.002 ? 1 - gone : 0, clip: C.inset(0, 100 * (1 - sc), 0, 0) });
      K.eyebrowRun(t, S.scopeL, 69.5, 71.2);
    },
  });

  // ------------------------------------------------------------------ 9 · agents: seven agents, one team (b72 → b80)
  const AGENTS = [
    ['Scout', 'Map the attack surface', 'Red team'], ['Probe', 'Prove or disprove', 'Red team'], ['Trace', 'Follow the path', 'Red team'],
    ['Diagnose', 'Find the root cause', 'Blue team'], ['Patch', 'Propose the smallest fix', 'Blue team'], ['Fortify', 'Prevent recurrence', 'Blue team'],
    ['Verify', 'Accept on evidence', 'Independent'],
  ];
  const DEAL = [73, 73.5, 74, 75, 75.5, 76, 77];
  scene({
    name: 'agents', from: 'agents', to: 'walk',
    build(root, S) {
      S.bg = K.ink(root);
      S.cam = full(root);
      S.eye = K.eyebrow(S.cam, 'The security team', PAD, 170, 'var(--ember)');
      S.t1 = K.head(S.cam, 'SEVEN AGENTS.', PAD, 226, 120, { color: '#fff' });
      S.cards = AGENTS.map(([name, role, team], i) => {
        const red = team === 'Red team', ver = team === 'Independent';
        const c = el('div', { class: 'abs', style: `left:${PAD + i * 236}px;top:430px;width:220px;height:350px;border-radius:20px;background:${ver ? '#22301f' : '#2b1d19'};` +
          `box-shadow:0 0 0 1px ${red ? 'rgba(224,104,74,.45)' : ver ? 'rgba(79,191,135,.45)' : 'rgba(255,255,255,.12)'};color:#fff;transform-origin:50% 100%` }, S.cam,
          `<div style="position:absolute;left:22px;top:20px;font:500 19px Mono;letter-spacing:.06em;text-transform:uppercase;color:${red ? 'var(--ember)' : ver ? 'var(--ok-dark)' : 'rgba(255,255,255,.55)'}">${team}</div>` +
          `<div style="position:absolute;right:22px;top:20px;font:500 19px Mono;color:rgba(255,255,255,.35)">0${i + 1}</div>` +
          `<div class="mark" style="position:absolute;left:22px;top:92px;width:76px;height:54px;color:${red ? 'var(--ember)' : ver ? 'var(--ok-dark)' : '#fff'}"></div>` +
          `<div style="position:absolute;left:22px;top:178px;font:700 40px Display;letter-spacing:-.03em">${name}</div>` +
          `<div style="position:absolute;left:22px;top:236px;width:176px;font:400 25px UI;line-height:1.25;color:rgba(255,255,255,.68)">${role}</div>`);
        return reg(c, { o: 0 });
      });
      S.cap = K.text(S.cam, 'Separate agents, each its own tool loop with enforced permissions.', PAD, 836, { size: 36, color: 'rgba(255,255,255,.78)', w: 1400 });
    },
    run(t, b, S) {
      K.inkRun(t, S.bg, 0.6, 115);
      put(S.cam, K.aim(W / 2, H / 2, 1.0 + 0.04 * ease.inOut(seg(t, 72, 80))));
      K.eyebrowRun(t, S.eye, 72);
      rise(t, S.t1, [72.25, 72.75]);
      S.cards.forEach((c, i) => {
        const p = spHit(t, DEAL[i], 'snappy');
        put(c, { o: p > 0.002 ? 1 : 0, y: 140 * (1 - p), r: 5 * (1 - p), s: 0.9 + 0.1 * p });
      });
      K.textRun(t, S.cap, 'perm');
    },
  });

  // ------------------------------------------------------------------ 10 · walk: one finding, start to proof (b80 → b88)
  const STEPS = [['Map the surface', 'Scout', 81], ['Chain the evidence', 'Probe · Trace', 83], ['Find the root cause', 'Diagnose', 86.5], ['Fix and prove it', 'Patch · Verify', 88.5]];
  const PX = 1000, PY = 420, PW = 780, PH = 470, KK = PW / 360;                       // panel: the site's 360x200 svg, scaled
  const ROWS = [[40, 'api'], [100, 'payments'], [160, 'ledger']], PN = [[70, 40], [150, 100], [235, 40], [300, 160]];
  scene({
    name: 'walk', from: 'walk', to: 'fix', pre: 1,
    build(root, S) {
      S.bg = K.paper(root);
      S.cam = full(root);
      S.eye = K.eyebrow(S.cam, 'One finding, start to proof', PAD, 170);
      S.t1 = K.head(S.cam, 'FOUR HARMLESS STEPS.', PAD, 226, 96, { color: 'var(--ink)' });
      S.t2 = K.head(S.cam, 'ONE VERIFIED FIX.', PAD, 326, 96, { color: 'var(--muted)' });
      S.steps = STEPS.map(([title, who], i) => reg(el('div', { class: 'abs', style: `left:${PAD}px;top:${470 + i * 104}px;width:780px;height:88px;border-left:5px solid var(--line);padding-left:28px;box-sizing:border-box` }, S.cam,
        `<div style="font:600 38px UI;letter-spacing:-.02em;color:var(--ink);margin-top:8px">${title}</div><div class="eyebrow" style="position:absolute;right:0;top:20px;font-size:24px;color:var(--faint)">${who}</div>`), { o: 0 }));
      S.panel = reg(el('div', { class: 'abs', style: `left:${PX}px;top:${PY}px;width:${PW}px;height:${PH}px;border-radius:22px;background:var(--ink);overflow:hidden;box-shadow:0 50px 110px -40px rgba(28,18,16,.6)` }, S.cam), { o: 0 });
      S.pctx = canvas(S.panel);
      S.pctx.canvas.style.width = PW + 'px'; S.pctx.canvas.style.height = PH + 'px';
      S.pctx.canvas.width = PW; S.pctx.canvas.height = PH;
      S.path = K.path(PN.map(([x, y]) => ({ x: 20 + x * KK, y: 22 + y * KK })));
    },
    run(t, b, S) {
      K.paperRun(t, S.bg);
      const wp = K.wipe(t, 79, 80);                                                  // the ant pulls this page in (fx overlay)
      put(S.root, { clip: wp < 1 ? C.inset(0, 100 * (1 - wp), 0, 0) : 'none' });
      const dive = ease.expoIn(seg(t, 87.2, 88));                                    // push into the panel
      put(S.cam, K.aim(lerp(W / 2, PX + PW / 2, dive), lerp(H / 2, PY + PH / 2, dive), 1 + 0.03 * seg(t, 80, 87) + 1.7 * dive));
      K.eyebrowRun(t, S.eye, 78.6);
      rise(t, S.t1, [78.6, 78.7, 78.8]);
      rise(t, S.t2, [78.9, 79, 79.1]);
      const act = b < 83 ? 0 : b < 86.5 ? 1 : 2;
      S.steps.forEach((s, i) => {
        const p = sp(t, 78.8 + i * 0.1, 'default');
        const on = i === act ? 1 : 0, done = i < act;
        put(s, { o: p > 0.002 ? (on ? 1 : done ? 0.75 : 0.38) : 0, x: -30 * (1 - p), css: { borderLeftColor: on ? 'var(--accent)' : done ? 'var(--ink)' : 'var(--line)' } });
      });
      const pp = sp(t, 78.7, 'default');
      put(S.panel, { o: pp > 0.002 ? 1 : 0, y: 60 * (1 - pp) });
      // panel canvas: rows of code activity, Scout's scan, Probe's three harmless steps, Trace's path, Diagnose's root
      const g = S.pctx; g.clearRect(0, 0, PW, PH);
      const scan = seg(t, 81, 82.5);
      g.font = '500 22px Mono'; g.textBaseline = 'alphabetic';
      for (const [y, label] of ROWS) {
        g.fillStyle = 'rgba(255,255,255,.45)'; g.fillText(label, 20 + 8 * KK, 22 + (y - 14) * KK);
        for (let k = 0; k < 34; k++) {
          const bx = 20 + (8 + k * 10.3) * KK, lit = clamp((scan * 360 - (8 + k * 10.3)) / 30 + 1) * (scan > 0 ? 1 : 0);
          const base = 0.25 + ((k * 7 + y) % 5) * 0.08;
          g.fillStyle = lit > 0 && scan < 1 && scan * 360 - (8 + k * 10.3) < 30 ? 'rgba(224,104,74,.95)' : `rgba(255,255,255,${(base * (0.35 + 0.65 * lit)).toFixed(3)})`;
          g.fillRect(bx, 22 + (y - 8) * KK, 2 * KK, 16 * KK);
        }
      }
      if (scan > 0 && scan < 1) { g.fillStyle = 'rgba(224,104,74,.18)'; g.fillRect(20 + scan * 360 * KK - 40, 0, 40, PH); }
      // Trace draws the path through the steps to the root
      const tr = ease.inOut(seg(t, 85, 86.25));
      if (tr > 0) { g.save(); g.strokeStyle = b < 86.5 ? 'rgba(224,104,74,.95)' : '#ff6a52'; g.lineWidth = 3.5; g.lineJoin = 'round'; K.strokeSpan(g, S.path, 0, S.path.length * tr, 3); g.restore(); }
      PN.forEach(([x, y], i) => {
        const at = [83, 83.5, 84, 86.5][i], p = spHit(t, at, 'snappy');
        if (p <= 0.002) return;
        const cx = 20 + x * KK, cy = 22 + y * KK, root = i === 3;
        const ring = t > bt(at) ? Math.exp(-(t - bt(at)) * 4) : 0;
        if (ring > 0.02) { g.strokeStyle = `rgba(255,255,255,${ring.toFixed(3)})`; g.lineWidth = 2; g.beginPath(); g.arc(cx, cy, 12 + 30 * (1 - ring), 0, Math.PI * 2); g.stroke(); }
        g.fillStyle = root ? '#ff6a52' : '#fff'; g.beginPath(); g.arc(cx, cy, (root ? 14 : 11) * p, 0, Math.PI * 2); g.fill();
      });
      const lab = spHit(t, 87, 'snappy');
      if (lab > 0.002) { g.globalAlpha = clamp(lab * 1.4); g.font = '600 24px Mono'; g.fillStyle = '#ff8a78'; g.textAlign = 'right'; g.fillText('root cause · create_refund', PW - 26, 22 + 186 * KK - 6 + 10 * (1 - lab)); g.textAlign = 'left'; g.globalAlpha = 1; }
    },
  });

  // ------------------------------------------------------------------ 11 · fix: diagnose, repair, verify (b88 → b104)
  // The commit's real diff and the reviewer's repair (frontend/lib/demo/scenarios.ts, refund bound / CWE-840).
  const DIFF = [
    ['h', '@@ -151,9 +151,11 @@ def create_refund('],
    [' ', '        p = store.payments.get(body.payment_id)'],
    [' ', '        if p is None:'],
    [' ', '            raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")'],
    [' ', '        require_owner(p.customer_id, customer)'],
    ['-', '        if store.refunds_for(p.id):'],
    ['-', '            raise HTTPException(status.HTTP_409_CONFLICT, "already refunded")'],
    ['+', '        # Partial refunds: several refunds may be issued for one payment.'],
    ['+', '        if body.amount > p.amount:'],
    ['+', '            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "refund exceeds payment")'],
  ];
  const PATCH = [
    ['h', '@@ -155,3 +155,4 @@ def create_refund('],
    ['+', '        already = sum((r.amount for r in store.refunds_for(p.id)), Decimal("0"))'],
    ['-', '        if body.amount > p.amount:'],
    ['+', '        if already + body.amount > p.amount:'],
    [' ', '            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "refund exceeds payment")'],
  ];
  const FL = 42, FX = PAD, FY = 190, FWD = 1640;
  const diffLine = (parent, [k, s], i, y0) => {
    const col = k === '+' ? 'var(--ok-dark)' : k === '-' ? '#ff8a78' : k === 'h' ? 'rgba(255,255,255,.4)' : 'rgba(255,255,255,.82)';
    const bg = k === '+' ? 'rgba(79,191,135,.10)' : k === '-' ? 'rgba(224,104,74,.12)' : 'transparent';
    return reg(el('div', { class: 'abs mono', style: `left:0;top:${y0 + i * FL}px;width:${FWD}px;height:${FL}px;line-height:${FL}px;font-size:25px;white-space:pre;background:${bg};color:${col}` }, parent,
      `<span style="display:inline-block;width:56px;text-align:center;opacity:.8">${k === 'h' ? '' : k}</span>${s.replace(/</g, '&lt;')}`), { o: 0 });
  };
  scene({
    name: 'fix', from: 'fix', to: 'monitor',
    build(root, S) {
      S.bg = K.ink(root);
      S.cam = full(root);
      S.stack = reg(el('div', { class: 'abs', style: `width:${W}px;height:${H}px;transform-origin:${W / 2}px ${H / 2}px` }, S.cam));
      S.eyes = [['Diagnose · root cause', 88], ['Patch · the smallest fix', 'patch'], ['Verify · fresh checkout', 'verify']].map(([s]) => K.eyebrow(S.stack, s, PAD, 120, 'var(--ember)'));
      S.code = reg(el('div', { class: 'abs', style: `left:${FX}px;top:${FY}px;width:${FWD}px;height:${DIFF.length * FL + 40}px;border-radius:20px;background:#211613;overflow:hidden;box-shadow:0 0 0 1px rgba(255,255,255,.07)` }, S.stack), { o: 0 });
      S.dl = DIFF.map((d, i) => diffLine(S.code, d, i, 20));
      S.pl = PATCH.map((d, i) => diffLine(S.code, d, i, 20));
      S.rootBox = reg(el('div', { class: 'abs', style: `left:0;top:${20 + 5 * FL}px;width:${FWD}px;height:${2 * FL}px;box-shadow:inset 0 0 0 3px #ff6a52;border-radius:6px` }, S.code), { o: 0 });
      S.why = K.text(S.stack, 'Root cause: the <b style="color:#fff;font-weight:600">“already refunded”</b> check was removed without a running-total check.', PAD, 690, { size: 38, color: 'rgba(255,255,255,.78)', w: 1640 });
      S.ver = K.win(S.stack, { x: 980, y: 520, w: 800, file: 'verify · fresh checkout', size: 26, lines: [
        ['ok', 'exploit replay: 201, 422', 'total 60.00'], ['ok', '33 tests passed', '30 + 3 generated'], ['ok', 'Verify accepted the repair', '']] });
      S.v1 = K.head(S.cam, 'NOTHING MERGES', PAD, 330, 150, { color: '#fff' });
      S.v2 = K.head(S.cam, 'AUTOMATICALLY.', PAD, 490, 150, { color: 'var(--ember)' });
      S.pr = K.text(S.cam, 'A pull request with the verified fix is waiting for your team.', PAD + 4, 700, { size: 40, color: 'rgba(255,255,255,.82)', w: 1400 });
    },
    run(t, b, S) {
      K.inkRun(t, S.bg, 0.25 + 0.35 * sp(t, 'verify', 'heavy'), 116);
      put(S.cam, K.aim(W / 2, H / 2, 1.03 - 0.03 * ease.out(seg(t, 88, 92)) + 0.06 * ease.inOut(seg(t, 96.5, 104))));   // the hold keeps moving
      S.eyes.forEach((e, i) => K.eyebrowRun(t, e, [87.9, 'patch', 'verify'][i], [91.75, 93.75, 96.6][i]));
      const c = spHit(t, 88, 'default');
      put(S.code, { o: c > 0.002 ? 1 : 0, y: 50 * (1 - c), css: { height: `${(b < 92 ? DIFF.length : PATCH.length) * FL + 40}px` } });
      // diagnose: the commit diff builds, the removed guard gets boxed
      S.dl.forEach((ln, i) => { const p = spHit(t, 88 + i * 0.0625, 'snappy'), q = sp(t, 91.82, 'snappy'); put(ln, { o: p > 0.002 && q < 0.99 ? 1 - q : 0, x: -20 * (1 - p) }); });
      const rb = spHit(t, 89.5, 'snappy');
      put(S.rootBox, { o: rb > 0.002 && b < 91.9 ? 1 : 0, s: 1 + 0.03 * (1 - rb), css: { transformOrigin: '50% 50%' } });
      K.textRun(t, S.why, 90, 91.7);
      // repair: the patch lines type on (only + lines type; context and − lines snap in)
      S.pl.forEach((ln, i) => {
        const k = PATCH[i][0], at = 'patch', p = spHit(t, beatOf(at) - 0.08 + i * 0.12, 'snappy');
        const body = PATCH[i][1];
        const n = k === '+' ? Math.floor(seg(t, beatOf(at) + i * 0.4, beatOf(at) + i * 0.4 + 0.75) * body.length) : body.length;
        put(ln, { o: p > 0.002 ? 1 : 0, html: `<span style="display:inline-block;width:56px;text-align:center;opacity:.8">${k === 'h' ? '' : k}</span>${body.slice(0, n).replace(/</g, '&lt;')}` });
      });
      // verify: the window rises over the patch; rows land on beats
      K.winRun(t, S.ver, 94, [94.5, 95, 95.5], 96.6);
      // the code steps back for the line that matters
      const back = sp(t, 96.5, 'heavy');
      put(S.stack, { s: 1 - 0.08 * back, filter: back > 0.01 ? `brightness(${(1 - 0.72 * back).toFixed(3)}) blur(${(5 * back).toFixed(2)}px)` : 'none', o: 1 - sp(t, 103.5, 'default') });
      rise(t, S.v1, [97, 97.5], 103.6, { exit: 0.3 });
      rise(t, S.v2, [98, 98.5], 103.6, { exit: 0.3 });
      K.textRun(t, S.pr, 99.5, 103.4);
    },
  });

  // ------------------------------------------------------------------ 12 · monitor: keep it secure, the loop closes (b104 → b112)
  const RC = { x: 1390, y: 560 }, RR = 290;
  scene({
    name: 'monitor', from: 'monitor', to: 'build2',
    build(root, S) {
      S.bg = K.ink(root);
      S.cam = full(root);
      S.ctx = canvas(S.cam);
      S.eye = K.eyebrow(S.cam, '04 · Monitor and retest', PAD, 200, 'var(--ember)');
      S.t1 = K.head(S.cam, 'KEEP IT', PAD, 262, 112, { color: '#fff' });
      S.t2 = K.head(S.cam, 'SECURE.', PAD, 382, 112, { color: 'var(--ember)' });
      S.win = K.win(S.cam, { x: PAD, y: 560, w: 860, file: 'events', size: 25, lines: [
        ['ok', 'push · main · signature verified', ''], ['run', 're-assessment queued', ''], ['q', 'policy advice (test-environment-trained)', 'not auto-applied']] });
      S.ring = K.trail((a) => ({ x: Math.cos(a - Math.PI / 2), y: Math.sin(a - Math.PI / 2) }), RR, RR, 600, RC.x, RC.y);
      // each chip hangs centred on a zero-size pin that sits on the ring (the pin moves; the chip keeps its CSS centring)
      S.pins = K.LOOP.map(() => reg(el('div', { class: 'abs' }, S.cam)));
      S.chips = K.LOOP.map((s, i) => { const c = K.chip(S.pins[i], i + 1, s, 22); c.style.transform = 'translate(-50%, -50%)'; return c; });
      S.mid = K.text(S.cam, 'Every finding feeds the next test.', RC.x - 170, RC.y - 40, { size: 32, color: 'rgba(255,255,255,.85)', w: 340, lh: 1.25 });
      S.mid.style.textAlign = 'center';
    },
    run(t, b, S) {
      K.inkRun(t, S.bg, 0.45, 112, 72);
      const dive = ease.expoIn(seg(t, 111, 112));
      put(S.cam, K.aim(lerp(W / 2, RC.x, dive), lerp(H / 2, RC.y, dive), 1 + 0.03 * seg(t, 104, 111) + 5 * dive));
      K.eyebrowRun(t, S.eye, 104);
      rise(t, S.t1, [104.25, 104.5]);
      rise(t, S.t2, [104.75]);
      K.winRun(t, S.win, 104.75, [105.5, 106, 106.5]);
      // the loop: chips sit on a ring; a light runs round it; ants march the ring like a trail
      const g = S.ctx; g.clearRect(0, 0, W, H);
      const rp = ease.inOut(seg(t, 104.5, 106.5));
      g.save(); g.strokeStyle = 'rgba(255,255,255,.12)'; g.lineWidth = 2; K.strokeSpan(g, S.ring, 0, S.ring.length * rp, 4); g.restore();
      const lit = b < 107 ? -1 : Math.floor((b - 107) * 2) % 7;
      S.chips.forEach((c, i) => {
        const a = (i / 7) * Math.PI * 2 - Math.PI / 2, p = spHit(t, 105 + i * 0.25, 'snappy');
        const x = RC.x + Math.cos(a) * RR, y = RC.y + Math.sin(a) * RR;
        put(S.pins[i], { x, y, s: 0.8 + 0.2 * p });
        put(c, { o: p > 0.002 ? 1 : 0, css: { background: i === lit ? 'var(--accent)' : 'rgba(43,29,25,.96)', color: i === lit ? '#fff' : 'rgba(255,255,255,.88)', boxShadow: '0 0 0 1px rgba(255,255,255,.1)' } });
      });
      if (b > 106) {
        const tc = t - bt(106);
        for (let k = 0; k < 14; k++) K.antOn(g, S.ring, (k / 14) * S.ring.length + tc * 150, 1, { t: tc, lane: ((k * 7) % 5 - 2) * 4, seed: (k * 0.37) % 1, phase: k, scale: 1.7, alpha: clamp(tc * 2 - k * 0.08), color: k === 0 ? K.SCOUT : K.ANT });
      }
      K.textRun(t, S.mid, 108, null, 16);
    },
  });
})();
