// CHAPTER 1: THE CODE REVIEWER. Plain words, one idea per screen: learn the rules, check every change against them,
// prove the bug with a test, write the smallest fix, show the real review. Content: the refund bound defect from
// examples/payments-lite and the demo run on lumen-pay/payments-api (frontend/lib/demo/scenarios.ts).
(() => {
  const { W, H, el, reg, put, scene, canvas, sp, spHit, seg, clamp, lerp, ease, bt, beatOf } = C;
  const { rise } = TYPE;
  const PAD = K.PAD, TAG = '01 · The Code Reviewer';
  const full = (root) => reg(el('div', { class: 'abs', style: `width:${W}px;height:${H}px` }, root));

  // ------------------------------------------------------------------ learn the rules (b68 → b84)
  const NODES = (() => {
    const r = C.mulberry32(56), n = [];
    for (const [label, x, y] of [['app.py', 0.18, 0.2], ['create_refund', 0.42, 0.34], ['store.py', 0.72, 0.18], ['refunds_for', 0.85, 0.42], ['require_owner', 0.2, 0.58], ['README', 0.55, 0.62], ['tests', 0.82, 0.78], ['docstring', 0.3, 0.86]]) n.push({ label, x, y });
    for (let i = 0; i < 22; i++) n.push({ label: '', x: 0.05 + r() * 0.9, y: 0.06 + r() * 0.88 });
    const e = []; n.forEach((a, i) => { const d = n.map((bb, j) => [Math.hypot(a.x - bb.x, a.y - bb.y), j]).sort((p, q) => p[0] - q[0]); for (const [, j] of d.slice(1, 3)) if (i < j) e.push([i, j]); });
    return { n, e };
  })();
  const GX = 1000, GY = 330, GW = 780, GH = 600;
  scene({
    name: 'c1_intent', from: 'c1_intent', to: 'c1_flaw',
    build(root, S) {
      S.bg = K.paper(root);
      S.cam = full(root);
      S.ctx = canvas(S.cam);
      S.tag = K.tag(S.cam, TAG, 'var(--accent)');
      S.s1 = K.say(S.cam, ['First, Ari learns what your', 'software is supposed to do.'], PAD, 140, { size: 60, color: 'var(--ink)' });
      S.s2 = K.say(S.cam, ['It reads your docs, comments and', 'tests, and writes down the rules.'], PAD, 140, { size: 60, color: 'var(--ink)' });
      S.s3 = K.say(S.cam, ['Like this one: refunds can never', 'add up to more than the payment.'], PAD, 140, { size: 60, color: 'var(--ink)', hl: ['never'], hlc: 'var(--accent)' });
      S.win = K.win(S.cam, { x: 140, y: 470, w: 900, file: 'the rules Ari learned', size: 30, lines: [
        ['ok', 'Total refunds ≤ the payment', 'from the docs'], ['ok', 'Discounts round half-up', 'from a test'], ['q', 'Only the owner can refund', 'inferred']] });
      S.win.box.style.transformOrigin = '50% 100%';
    },
    run(t, b, S) {
      K.paperRun(t, S.bg);
      put(S.cam, K.aim(W / 2, H / 2, 1.03 - 0.03 * ease.out(seg(t, 68, 76))));
      K.eyebrowRun(t, S.tag, 67.8);
      K.sayRun(t, S.s1, 68.5, 73.6);
      K.sayRun(t, S.s2, 74, 79.6);
      K.sayRun(t, S.s3, 80);
      K.winRun(t, S.win, 75, [76.5, 77.5, 78.5]);
      const hl = spHit(t, 80.5, 'snappy');
      put(S.win.rows[0], { css: { background: hl > 0.5 ? 'rgba(194,69,45,.1)' : 'transparent', boxShadow: hl > 0.5 ? 'inset 6px 0 0 var(--accent)' : 'none' } });
      const g = S.ctx; g.clearRect(0, 0, W, H);
      const scan = seg(t, 68.6, 71.5);
      g.lineWidth = 1.5;
      for (const [i, j] of NODES.e) {
        const a = NODES.n[i], c = NODES.n[j], k = clamp((scan * 1.15 - Math.max(a.x, c.x)) * 6); if (k <= 0) continue;
        g.strokeStyle = `rgba(28,18,16,${(0.16 * k).toFixed(3)})`; g.beginPath(); g.moveTo(GX + a.x * GW, GY + a.y * GH); g.lineTo(GX + lerp(a.x, c.x, k) * GW, GY + lerp(a.y, c.y, k) * GH); g.stroke();
      }
      g.font = '500 24px Mono'; g.textBaseline = 'middle';
      NODES.n.forEach((nd) => {
        const k = clamp((scan * 1.15 - nd.x) * 8); if (k <= 0) return;
        const x = GX + nd.x * GW, y = GY + nd.y * GH, hot = ['create_refund', 'docstring', 'README', 'tests'].includes(nd.label);
        g.fillStyle = hot ? `rgba(194,69,45,${k})` : `rgba(28,18,16,${(0.55 * k).toFixed(3)})`;
        g.beginPath(); g.arc(x, y, (nd.label ? 8 : 5) * (0.6 + 0.4 * k), 0, Math.PI * 2); g.fill();
        if (nd.label) { g.fillStyle = hot ? `rgba(194,69,45,${k})` : `rgba(107,87,82,${k})`; g.fillText(nd.label, x + 15, y); }
      });
    },
  });

  // ------------------------------------------------------------------ check every change against the rules (b84 → b112)
  const CODE = [['', 'def create_refund(body, customer, store):'], ['i', '    """Refund part or all of a payment.'], ['i', '    Total refunds must never exceed'],
    ['i', '    the payment\'s original amount."""'], ['', '    p = store.payments.get(body.payment_id)'], ['', '    require_owner(p.customer_id, customer)'],
    ['x', '    if body.amount > p.amount:'], ['x', '        raise HTTPException(422, "refund exceeds payment")']];
  const LH = 44, CY0 = 500, CWD = 1060;
  scene({
    name: 'c1_flaw', from: 'c1_flaw', to: 'c1_prove',
    build(root, S) {
      S.bg = K.ink(root);
      S.cam = full(root);
      S.tag = K.tag(S.cam, TAG);
      S.s1 = K.say(S.cam, ['Then, every time someone changes', 'the code, Ari checks the rules.'], PAD, 130, { size: 56 });
      S.s2 = K.say(S.cam, ['This change let customers refund', 'more than they paid.'], PAD, 130, { size: 56, hl: ['more', 'than', 'they', 'paid.'] });
      S.s3 = K.say(S.cam, ['The usual automated checks passed.', 'Ari still caught it.'], PAD, 130, { size: 56, hl: ['Ari', 'still', 'caught', 'it.'] });
      S.commit = reg(el('div', { class: 'abs', style: `left:${PAD}px;top:330px;width:1640px;height:128px;border-radius:20px;background:#2b1d19;box-shadow:0 0 0 1px rgba(255,255,255,.08);color:#fff;transform-origin:50% 0` }, S.cam,
        `<span style="position:absolute;left:30px;top:30px;width:68px;height:68px;border-radius:50%;background:var(--accent);display:grid;place-items:center;font:600 24px UI">PN</span>` +
        `<span style="position:absolute;left:124px;top:22px;font:600 44px UI;letter-spacing:-.02em">feat(refunds): allow partial refunds</span>` +
        `<span style="position:absolute;left:126px;top:80px;font:400 24px Mono;color:rgba(255,255,255,.5)">A real change to a payments app · priya-natarajan · main</span>` +
        `<span style="position:absolute;right:30px;top:38px;font:500 28px Mono;color:var(--ok-dark);background:rgba(79,191,135,.12);padding:12px 18px;border-radius:10px">✓ Tests passed</span>`), { o: 0 });
      S.code = reg(el('div', { class: 'abs', style: `left:${PAD}px;top:${CY0}px;width:${CWD}px;height:${CODE.length * LH + 48}px;border-radius:20px;background:#211613;box-shadow:0 0 0 1px rgba(255,255,255,.07)` }, S.cam), { o: 0 });
      S.hiI = reg(el('div', { class: 'abs', style: `left:0;top:${24 + 1 * LH}px;width:${CWD}px;height:${3 * LH}px;background:rgba(79,191,135,.13);border-left:6px solid var(--ok-dark);transform-origin:0 50%` }, S.code), { o: 0 });
      S.hiX = reg(el('div', { class: 'abs', style: `left:0;top:${24 + 6 * LH}px;width:${CWD}px;height:${LH}px;background:rgba(224,104,74,.2);border-left:6px solid var(--ember);transform-origin:0 50%` }, S.code), { o: 0 });
      S.lines = CODE.map(([k, s], i) => reg(el('div', { class: 'abs mono', style: `left:40px;top:${24 + i * LH}px;font-size:27px;line-height:${LH}px;white-space:pre;color:${k === 'i' ? 'rgba(255,255,255,.6)' : 'rgba(255,255,255,.88)'}` }, S.code, s), { o: 0 }));
      S.tagI = reg(el('div', { class: 'abs eyebrow', style: `left:${CWD - 190}px;top:${24 + 2 * LH + 8}px;color:var(--ok-dark);font-size:24px` }, S.code, 'The rule'), { o: 0 });
      S.tagX = reg(el('div', { class: 'abs eyebrow', style: `left:560px;top:${24 + 6 * LH + 8}px;color:var(--ember);font-size:24px` }, S.code, 'Only checks one refund'), { o: 0 });
      const MX = PAD + CWD + 40, MW = 1780 - MX;
      S.math = reg(el('div', { class: 'abs', style: `left:${MX}px;top:${CY0}px;width:${MW}px;height:${CODE.length * LH + 48}px;border-radius:20px;background:#2b1d19;box-shadow:0 0 0 1px rgba(255,255,255,.08);color:#fff` }, S.cam), { o: 0 });
      el('div', { class: 'abs eyebrow', style: 'left:30px;top:28px;color:rgba(255,255,255,.5);font-size:22px' }, S.math, 'What a customer could do');
      const row = (y, a, bb, c, cc) => reg(el('div', { class: 'abs', style: `left:30px;top:${y}px;width:${MW - 60}px;display:flex;font:500 32px UI;line-height:42px` }, S.math,
        `<span style="flex:1;color:rgba(255,255,255,.75)">${a}</span><span class="mono" style="width:150px;text-align:right">${bb}</span><span style="width:70px;text-align:right;color:${cc}">${c}</span>`), { o: 0 });
      S.r0 = row(84, 'Pay', '$100', '', '#fff'); S.r1 = row(140, 'Refund', '$60', '✓', 'var(--ok-dark)'); S.r2 = row(196, 'Refund', '$60', '✓', 'var(--ok-dark)');
      S.r3 = row(270, 'Refunded', '$120', '✕', '#ff8a78');
      S.barW = MW - 60;
      S.bar = reg(el('div', { class: 'abs', style: `left:30px;top:350px;width:${S.barW}px;height:22px;border-radius:11px;background:rgba(255,255,255,.08)` }, S.math), { o: 0 });
      S.fill = reg(el('div', { class: 'abs', style: `left:30px;top:350px;width:${S.barW / 1.2}px;height:22px;border-radius:11px;background:var(--ok-dark);transform-origin:0 50%` }, S.math), { o: 0 });
      S.cap = reg(el('div', { class: 'abs', style: `left:${30 + S.barW / 1.2 - 2}px;top:338px;width:4px;height:46px;background:#fff` }, S.math), { o: 0 });
      S.capL = reg(el('div', { class: 'abs eyebrow', style: `left:${30 + S.barW / 1.2 - 140}px;top:392px;color:rgba(255,255,255,.6);font-size:22px` }, S.math, 'what they paid'), { o: 0 });
    },
    run(t, b, S) {
      K.inkRun(t, S.bg, 0.15 + 0.3 * sp(t, 103, 'heavy'), 120);
      put(S.cam, K.aim(W / 2, H / 2, 1.02 - 0.02 * ease.out(seg(t, 84, 92)) + 0.03 * ease.inOut(seg(t, 104, 112))));
      K.eyebrowRun(t, S.tag, 83.8);
      K.sayRun(t, S.s1, 84.5, 95.6);
      K.sayRun(t, S.s2, 96, 104.6);
      K.sayRun(t, S.s3, 105, 111.6);
      const c = sp(t, 86, 'default'); put(S.commit, { o: c > 0.002 ? 1 : 0, s: 0.92 + 0.08 * c, y: -30 * (1 - c) });
      const cd = sp(t, 88, 'default'); put(S.code, { o: cd > 0.002 ? 1 : 0, y: 50 * (1 - cd) });
      S.lines.forEach((ln, i) => { const p = spHit(t, 88.25 + i * 0.125, 'snappy'); put(ln, { o: p > 0.002 ? 1 : 0, x: -20 * (1 - p) }); });
      const hi = spHit(t, 91, 'snappy'), hx = spHit(t, 93.5, 'snappy');
      put(S.hiI, { o: hi > 0.002 ? 1 : 0, sx: hi }); put(S.tagI, { o: clamp(hi * 1.5) });
      put(S.hiX, { o: hx > 0.002 ? 1 : 0, sx: hx }); put(S.tagX, { o: clamp(hx * 1.5) });
      const m = sp(t, 96.5, 'default'); put(S.math, { o: m > 0.002 ? 1 : 0, y: 50 * (1 - m) });
      [[S.r0, 97.5], [S.r1, 99], [S.r2, 100.5], [S.r3, 102.5]].forEach(([r, at]) => { const p = spHit(t, at, 'snappy'); put(r, { o: p > 0.002 ? 1 : 0, x: -24 * (1 - p) }); });
      const bb = sp(t, 97.5, 'default');
      put(S.bar, { o: bb > 0.002 ? 1 : 0 }); put(S.cap, { o: bb > 0.002 ? 1 : 0 }); put(S.capL, { o: clamp(bb * 1.3) });
      const F = 0.6 * spHit(t, 99, 'snappy') + 0.6 * spHit(t, 100.5, 'snappy');      // refunded / paid
      put(S.fill, { o: F > 0.002 ? 1 : 0, sx: F, css: { background: F > 1.001 ? '#ff6a52' : 'var(--ok-dark)' } });
    },
  });

  // ------------------------------------------------------------------ prove it with a test (b112 → b128)
  scene({
    name: 'c1_prove', from: 'c1_prove', to: 'c1_fix',
    build(root, S) {
      S.bg = K.ink(root);
      S.cam = full(root);
      S.tag = K.tag(S.cam, TAG);
      S.s1 = K.say(S.cam, ['Ari doesn\'t just leave a comment.', 'It writes a test that proves the bug.'], PAD, 130, { size: 56, hl: ['proves'] });
      S.s2 = K.say(S.cam, ['If the test fails the same way twice,', 'it\'s real. If not, it\'s dropped.'], PAD, 130, { size: 56, hl: ['twice,'] });
      S.win = K.win(S.cam, { x: PAD, y: 420, w: 1060, file: 'sealed test copy of the app', size: 30, lines: [
        ['run', 'test written by Ari: refunds_cannot_exceed_payment', ''], ['bad', 'run 1', 'failed'], ['bad', 'run 2, same failure', 'failed'], ['ok', 'bug confirmed', 'validated']] });
      S.two = K.head(S.cam, '2×', 1330, 380, 300, { color: 'var(--ember)', cls: 'mono' });
      S.two.el.style.fontWeight = '600';
      S.twoL = K.text(S.cam, 'Proof, not opinion.', 1340, 720, { size: 38, color: 'rgba(255,255,255,.8)', w: 440, weight: 500 });
    },
    run(t, b, S) {
      K.inkRun(t, S.bg, 0.35, 116);
      put(S.cam, K.aim(W / 2, H / 2, 1 + 0.04 * ease.inOut(seg(t, 112, 128))));
      K.eyebrowRun(t, S.tag, 111.8);
      K.sayRun(t, S.s1, 112.5, 119.6);
      K.sayRun(t, S.s2, 120);
      K.winRun(t, S.win, 114, [115, 116.5, 118, 121.5]);
      rise(t, S.two, [120.5]);
      K.textRun(t, S.twoL, 122);
    },
  });

  // ------------------------------------------------------------------ the smallest fix, every test re-run (b128 → b144)
  const PATCH = [['h', 'payments_api/app.py · the fix'], ['+', '    already = sum(r.amount for r in store.refunds_for(p.id))'],
    ['-', '    if body.amount > p.amount:'], ['+', '    if already + body.amount > p.amount:']];
  const TESTS = [['A single partial refund works', 'pass', 'pass'], ['Refunds can\'t add up to more than the payment', 'fail', 'pass'], ['Refund amounts must be positive', 'pass', 'pass']];
  scene({
    name: 'c1_fix', from: 'c1_fix', to: 'c1_real',
    build(root, S) {
      S.bg = K.ink(root);
      S.cam = full(root);
      S.tag = K.tag(S.cam, TAG);
      S.s1 = K.say(S.cam, ['Then it writes the smallest fix', 'and runs every test again.'], PAD, 130, { size: 56 });
      S.s2 = K.say(S.cam, ['Nothing changes in your code until', 'a person on your team approves it.'], PAD, 130, { size: 56, hl: ['person'] });
      S.code = reg(el('div', { class: 'abs', style: `left:${PAD}px;top:340px;width:1640px;height:${PATCH.length * 48 + 36}px;border-radius:20px;background:#211613;box-shadow:0 0 0 1px rgba(255,255,255,.07);overflow:hidden` }, S.cam), { o: 0 });
      S.pl = PATCH.map(([k, s], i) => reg(el('div', { class: 'abs mono', style: `left:0;top:${18 + i * 48}px;width:1640px;height:48px;line-height:48px;font-size:28px;white-space:pre;` +
        `background:${k === '+' ? 'rgba(79,191,135,.10)' : k === '-' ? 'rgba(224,104,74,.12)' : 'transparent'};color:${k === '+' ? 'var(--ok-dark)' : k === '-' ? '#ff8a78' : 'rgba(255,255,255,.45)'}` }, S.code,
        `<span style="display:inline-block;width:60px;text-align:center">${k === 'h' ? '' : k}</span>${s}`), { o: 0 }));
      S.tbl = reg(el('div', { class: 'abs', style: `left:${PAD}px;top:620px;width:1640px;height:300px;border-radius:20px;background:#2b1d19;box-shadow:0 0 0 1px rgba(255,255,255,.08);color:#fff` }, S.cam,
        `<div class="eyebrow" style="position:absolute;left:30px;top:24px;font-size:22px;color:rgba(255,255,255,.5)">Tests Ari wrote</div><div class="eyebrow" style="position:absolute;left:1240px;top:24px;font-size:22px;color:rgba(255,255,255,.5)">Before</div><div class="eyebrow" style="position:absolute;left:1440px;top:24px;font-size:22px;color:rgba(255,255,255,.5)">After the fix</div>`), { o: 0 });
      S.rows = TESTS.map(([name], i) => reg(el('div', { class: 'abs', style: `left:30px;top:${80 + i * 70}px;width:1580px;height:56px;font:500 32px UI;line-height:56px;color:rgba(255,255,255,.9)` }, S.tbl, name), { o: 0 }));
      const pill = (txt, ok, x, y) => reg(el('div', { class: 'abs mono', style: `left:${x}px;top:${y}px;padding:6px 14px;border-radius:8px;font-size:26px;font-weight:600;background:${ok ? 'rgba(79,191,135,.15)' : 'rgba(255,106,82,.16)'};color:${ok ? 'var(--ok-dark)' : '#ff8a78'}` }, S.tbl, `${ok ? '✓' : '✕'} ${txt}`), { o: 0 });
      S.before = TESTS.map(([, a], i) => pill(a, a === 'pass', 1240, 88 + i * 70));
      S.aft = TESTS.map(([, , a], i) => pill(a, true, 1440, 88 + i * 70));
    },
    run(t, b, S) {
      K.inkRun(t, S.bg, 0.3 + 0.35 * sp(t, 137, 'heavy'), 114);
      put(S.cam, K.aim(W / 2, H / 2, 1 + 0.03 * ease.inOut(seg(t, 128, 144))));
      K.eyebrowRun(t, S.tag, 127.8);
      K.sayRun(t, S.s1, 128.5, 138.6);
      K.sayRun(t, S.s2, 139);
      const c = sp(t, 129.5, 'default'); put(S.code, { o: c > 0.002 ? 1 : 0, y: 40 * (1 - c) });
      S.pl.forEach((ln, i) => {
        const k = PATCH[i][0], p = spHit(t, 130 + i * 0.5, 'snappy'), body = PATCH[i][1];
        const n = k === '+' ? Math.floor(seg(t, 130 + i * 0.5, 131.2 + i * 0.5) * body.length) : body.length;
        put(ln, { o: p > 0.002 ? 1 : 0, html: `<span style="display:inline-block;width:60px;text-align:center">${k === 'h' ? '' : k}</span>${body.slice(0, n)}` });
      });
      const tb = sp(t, 133.5, 'default'); put(S.tbl, { o: tb > 0.002 ? 1 : 0, y: 50 * (1 - tb) });
      S.rows.forEach((r, i) => { const p = spHit(t, 134 + i * 0.5, 'snappy'); put(r, { o: p > 0.002 ? 1 : 0, x: -20 * (1 - p) }); });
      S.before.forEach((p0, i) => { const p = spHit(t, 134.25 + i * 0.5, 'snappy'); put(p0, { o: p > 0.002 ? 1 : 0, s: 0.85 + 0.15 * p }); });
      S.aft.forEach((p0, i) => { const p = spHit(t, i === 1 ? 137 : 136 + i * 0.25, 'snappy'); put(p0, { o: p > 0.002 ? 1 : 0, s: 0.8 + 0.2 * p, css: { transformOrigin: '50% 50%' } }); });
    },
  });

  // ------------------------------------------------------------------ the real review (b144 → b168)
  const SX = 720, SY = 120, SW = 1060, SH = 840;
  const CAM = [[144, { x: 960, y: 540, z: SW / 1920 }], [145.5, { x: 680, y: 475, z: 1.05 }], [150, { x: 650, y: 700, z: 1.2 }],
    [155, { x: 720, y: 1165, z: 1.05 }], [160, { x: 950, y: 1650, z: 0.98 }]];
  const CAPS = [[['This is the real review', 'your team sees in Ari.'], 144.5, 149.6], [['The rule it learned,', 'and where it came from.'], 150, 154.6],
    [['The exact line it', 'flagged, and why.'], 155, 159.6], [['Tests that failed before', 'the fix, and pass after.'], 160, null]];
  scene({
    name: 'c1_real', from: 'c1_real', to: 'c1_why',
    build(root, S) {
      S.bg = K.ink(root);
      S.cam = full(root);
      S.tag = K.tag(S.cam, TAG);
      S.caps = CAPS.map(([l]) => K.say(S.cam, l, PAD, 420, { size: 46, gap: 1.25 }));
      S.win = K.window(S.cam, [['tab_code.jpg', 0], ['tab_code_s1.jpg', 760]], { x: SX, y: SY, w: SW, h: SH, url: 'ari-ai-lake.vercel.app/demo/lumen-pay/payments-api' });
    },
    run(t, b, S) {
      K.inkRun(t, S.bg, 0.5, 110);
      K.eyebrowRun(t, S.tag, 143.8);
      CAPS.forEach(([, a, z], i) => K.sayRun(t, S.caps[i], a, z));
      K.windowRun(S.win, [0, 1], K.camAt(t, CAM), sp(t, 144, 'default'));
    },
  });

  // ------------------------------------------------------------------ why it's different (b168 → b180)
  scene({
    name: 'c1_why', from: 'c1_why', to: 'menu2',
    build(root, S) {
      S.bg = K.ink(root);
      S.cam = full(root);
      S.tag = K.tag(S.cam, TAG);
      S.l1 = K.head(S.cam, 'NO PROOF,', PAD, 290, 190, { color: '#fff' });
      S.l2 = K.head(S.cam, 'NO FINDING.', PAD, 480, 190, { color: 'var(--ember)' });
      S.sub = K.say(S.cam, ['Other AI reviewers give opinions.', 'Ari gives evidence.'], PAD, 750, { size: 52, hl: ['evidence.'] });
    },
    run(t, b, S) {
      K.inkRun(t, S.bg, 0.6, 112);
      put(S.cam, K.aim(W / 2, H / 2, 1 + 0.05 * ease.inOut(seg(t, 168, 180))));
      K.eyebrowRun(t, S.tag, 167.8, 179.2);
      rise(t, S.l1, [168.5, 169], 179.4, { exit: 0.3 });
      rise(t, S.l2, [170, 170.5], 179.4, { exit: 0.3 });
      K.sayRun(t, S.sub, 172.5, 179.3);
    },
  });
})();
