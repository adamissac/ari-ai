// ACT 1: the problem. Code changes every day; reviews see a diff, scans see a snapshot; one harmless-looking
// change ships a real flaw (the planted defect in examples/payments-lite: refunds are checked one at a time).
(() => {
  const { W, H, el, reg, put, scene, canvas, sp, spHit, trk, seg, clamp, lerp, ease, bt, beatOf } = C;
  const { rise } = TYPE;
  const PAD = K.PAD;

  // Real code: examples/payments-lite/target/payments_lite/app.py (signature condensed, docstring wrapped).
  const WALL = [
    '@app.get("/payments", response_model=list[PaymentOut])', 'def list_payments(customer, store) -> list[PaymentOut]:',
    '    """List the current customer\'s own payments."""', '    return [payment_out(store, p) for p in store.payments.values()', '            if p.customer_id == customer.id]', '',
    '@app.post("/payments", status_code=201)', 'def create_payment(body: PaymentIn, customer, store) -> PaymentOut:',
    '    p = Payment(store.next_id("pay"), customer.id, body.amount, body.currency)', '    store.payments[p.id] = p', '    return payment_out(store, p)', '',
    '@app.get("/payments/{payment_id}")', 'def get_payment(payment_id: str, customer, store) -> PaymentOut:', '    """Return one payment by id."""',
    '    p = store.payments.get(payment_id)', '    if p is None:', '        raise HTTPException(404, "not found")', '    return payment_out(store, p)', '',
    '@app.post("/refunds", status_code=201)', 'def create_refund(body: RefundIn, customer, store) -> RefundOut:',
    '    """Refund part or all of a payment the customer owns.', '', '    Total refunds for a payment must never exceed', '    the payment\'s original amount.', '    """',
    '    p = store.payments.get(body.payment_id)', '    if p is None:', '        raise HTTPException(404, "not found")', '    require_owner(p.customer_id, customer)',
    '    if body.amount > p.amount:', '        raise HTTPException(422, "refund exceeds payment amount")', '    r = Refund(store.next_id("ref"), p.id, body.amount)', '    store.refunds[r.id] = r', '',
    '@app.get("/refunds/{refund_id}")', 'def get_refund(refund_id: str, customer, store) -> RefundOut:', '    r = store.refunds.get(refund_id)', '    if r is None:',
    '        raise HTTPException(404, "not found")', '    require_owner(r.customer_id, customer)', '    return RefundOut(id=r.id, payment_id=r.payment_id)', '',
    'def require_owner(owner_id: str, customer: Customer) -> None:', '    if owner_id != customer.id:', '        raise HTTPException(403, "forbidden")',
  ];
  // Real demo commits on lumen-pay/payments-api (frontend/lib/demo/data.ts), oldest first.
  const COMMITS = [
    ['PN', 'docs: document the require_owner convention', 'priya-natarajan · 3 days ago'],
    ['AK', 'test: cover currency validation edge cases', 'akshar-koth · 2 days ago'],
    ['MO', 'refactor(store): extract refunds_for helper', 'mina-okafor · 1 day ago'],
    ['JP', 'feat(search): filter payments by description', 'jules-park · 22 hours ago'],
    ['DS', 'fix(customers): return 404 for unknown customer ids', 'devon-shah · 7 hours ago'],
    ['SL', 'chore(deps): bump pydantic to 2.12.4', 'sam-lindqvist · 4 hours ago'],
    ['PN', 'feat(refunds): allow partial refunds', 'priya-natarajan · 2 hours ago'],
    ['AK', 'feat(payments): add GET /payments/{payment_id} lookup', 'akshar-koth · 14 min ago'],
  ];
  const ARRIVE = [3, 4, 5, 5.5, 6, 6.5, 7, 7.5];

  // ------------------------------------------------------------------ 1 · open: code changes every day (b0 → b8)
  scene({
    name: 'open', from: 'open', to: 'week',
    build(root, S) {
      S.bg = K.ink(root);
      S.cam = reg(el('div', { class: 'abs', style: `width:${W}px;height:${H}px` }, root));
      S.wall = reg(el('div', { class: 'abs mono', style: `left:${PAD}px;top:40px;font-size:24px;line-height:38px;color:rgba(255,255,255,.075);white-space:pre` }, S.cam));
      S.wallLines = WALL.map((s) => el('div', {}, S.wall, s.replace(/</g, '&lt;') || ' '));
      S.hot = reg(S.wallLines[WALL.indexOf('    if body.amount > p.amount:')], {});
      S.l1 = K.head(S.cam, 'CODE CHANGES', PAD, 310, 145, { color: '#fff' });
      S.l2 = K.head(S.cam, 'EVERY DAY.', PAD, 462, 145, { color: 'var(--ember)' });
      S.sub = K.text(S.cam, 'Developers and AI agents ship new behaviour with every merge.', PAD, 668, { size: 36, color: 'rgba(255,255,255,.72)', w: 860 });
      S.feed = reg(el('div', { class: 'abs', style: 'left:1236px;top:0px;width:720px;height:1080px' }, S.cam));
      S.cards = COMMITS.map(([who, msg, meta], i) => {
        const c = el('div', { class: 'abs', style: `left:0;top:${930 - 128}px;width:720px;height:112px;border-radius:16px;background:#2b1d19;box-shadow:0 0 0 1px rgba(255,255,255,.07);display:flex;align-items:center;gap:22px;padding:0 26px;box-sizing:border-box;color:#fff` }, S.feed,
          `<span style="flex:none;width:52px;height:52px;border-radius:50%;background:${i === 6 ? 'var(--accent)' : '#4a2c25'};display:grid;place-items:center;font:600 20px UI">${who}</span>` +
          `<span style="flex:1;min-width:0"><span style="display:block;font:500 29px UI;letter-spacing:-.01em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${msg}</span>` +
          `<span style="display:block;margin-top:6px;font:400 21px Mono;color:rgba(255,255,255,.5)">${meta} · main</span></span>` +
          `<span style="flex:none;width:40px;height:40px;border-radius:50%;background:rgba(79,191,135,.14);color:var(--ok-dark);display:grid;place-items:center;font:600 22px UI;margin-right:48px">✓</span>`);
        return reg(c, { o: 0 });
      });
    },
    run(t, b, S) {
      K.inkRun(t, S.bg, 0.55 + 0.15 * seg(t, 0, 8), 122);
      put(S.cam, K.aim(W / 2, H / 2, 1 + 0.045 * ease.inOut(seg(t, -1, 8))));
      put(S.wall, { y: -520 * seg(t, -2, 9) });
      const hot = sp(t, 6, 'default');
      put(S.hot, { css: { color: `rgba(224,104,74,${(0.075 + 0.5 * hot).toFixed(3)})` } });
      rise(t, S.l1, [-0.4, 0.5]);
      rise(t, S.l2, [2, 2.5]);
      K.textRun(t, S.sub, 4);
      // feed: each arrival lifts the stack by one card; cards rise into the bottom slot
      const n = trk(t, [[0, 0], ...ARRIVE.map((a, k) => [a, k + 1, 'snappy'])]);   // cards arrived (springy)
      S.cards.forEach((c, i) => {
        const p = spHit(t, ARRIVE[i], 'snappy');
        put(c, { o: p > 0.002 ? 1 : 0, y: -(n - 1 - i) * 128 + 160 * (1 - p), s: 0.96 + 0.04 * p });
      });
    },
  });

  // ------------------------------------------------------------------ 2 · week: reviews see a diff, scans see a snapshot (b8 → b18)
  const TICK_X = [4, 11, 17, 26, 31, 39, 47, 55, 62, 70, 79, 88];        // frontend/components/story.tsx
  const CAUGHT_PR = [1], CAUGHT_SCAN = [6, 7], TARGET = 8;
  const TL_X = PAD, TL_W = 1640, TL_Y = 700;
  const tickX = (n) => TL_X + (TICK_X[n] / 100) * TL_W;
  scene({
    name: 'week', from: 'week', to: 'flaw',
    build(root, S) {
      S.bg = K.paper(root, true);
      S.cam = reg(el('div', { class: 'abs', style: `width:${W}px;height:${H}px` }, root));
      S.eye = K.eyebrow(S.cam, 'The problem', PAD, 150);
      S.ta = K.head(S.cam, 'REVIEWS SEE A DIFF.', PAD, 212, 120, { color: 'var(--ink)' });
      S.tb = K.head(S.cam, 'SCANS SEE A SNAPSHOT.', PAD, 212, 120, { color: 'var(--ink)' });
      S.ba = K.text(S.cam, 'A reviewer reads the lines that changed.', PAD, 372, { size: 36, color: 'var(--muted)' });
      S.bb = K.text(S.cam, 'A scanner checks a moment in time.', PAD, 372, { size: 36, color: 'var(--muted)' });
      S.rail = reg(el('div', { class: 'abs', style: `left:${TL_X}px;top:${TL_Y + 48}px;width:${TL_W}px;height:3px;background:var(--line);transform-origin:0 50%` }, S.cam));
      S.days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'].map((d, i) => reg(el('div', { class: 'abs eyebrow', style: `left:${TL_X + i * (TL_W / 4) - (i === 4 ? 40 : 0)}px;top:${TL_Y + 128}px;color:var(--faint);font-size:24px` }, S.cam, d), { o: 0 }));
      S.today = reg(el('div', { class: 'abs eyebrow', style: `left:${TL_X + TL_W - 92}px;top:${TL_Y - 62}px;color:var(--faint);font-size:24px` }, S.cam, 'Today'), { o: 0 });
      S.ticks = TICK_X.map((_, n) => reg(el('div', { class: 'abs', style: `left:${tickX(n) - 6}px;top:${TL_Y}px;width:12px;height:100px;border-radius:6px;background:var(--ink);transform-origin:50% 100%` }, S.cam), { o: 0 }));
      const pill = (txt, x) => reg(el('div', { class: 'abs eyebrow', style: `left:${x}px;top:${TL_Y - 76}px;padding:8px 14px;border-radius:8px;background:var(--ink);color:#fff;font-size:24px;transform-origin:20px 100%` }, S.cam, txt), { o: 0 });
      S.prPill = pill('PR review', tickX(1) - 20);
      S.scPill = pill('Scanner', tickX(6) - 20);
      // snapshot brackets around the two ticks the scanner sees (a viewfinder, not a flash)
      const bx0 = tickX(6) - 46, bx1 = tickX(7) + 46, by0 = TL_Y - 22, by1 = TL_Y + 122;
      S.brk = reg(el('div', { class: 'abs', style: `left:${bx0}px;top:${by0}px;width:${bx1 - bx0}px;height:${by1 - by0}px;transform-origin:50% 50%` }, S.cam), { o: 0 });
      for (const [l, tp] of [[1, 1], [0, 1], [1, 0], [0, 0]]) {
        el('div', { style: `position:absolute;${l ? 'left' : 'right'}:0;${tp ? 'top' : 'bottom'}:0;width:34px;height:34px;border:${'5px solid var(--accent)'};${l ? 'border-right:none' : 'border-left:none'};${tp ? 'border-bottom:none' : 'border-top:none'}` }, S.brk);
      }
      S.count = reg(el('div', { class: 'abs eyebrow', style: `left:${PAD}px;top:${TL_Y - 160}px;padding:10px 16px;border-radius:8px;background:var(--accent);color:#fff;font-size:26px;transform-origin:0 100%` }, S.cam, '3 of 12 changes checked'), { o: 0 });
      // the dive: an ink block grows out of the unchecked target tick until it fills the frame
      S.grow = reg(el('div', { class: 'abs', style: 'width:1px;height:1px;background:var(--ink)' }, root), { o: 0 });
    },
    run(t, b, S) {
      K.paperRun(t, S.bg);
      // camera: settle, then lean toward the target tick while the ink grows out of it
      const dive = ease.expoIn(seg(t, 16, 17.9));
      const z = 1 + 0.06 * ease.out(seg(t, 8, 16)) + 1.4 * dive;
      const cam = K.aim(lerp(W / 2, tickX(TARGET), dive), lerp(H / 2, TL_Y + 50, dive), z, W / 2, H / 2);
      put(S.cam, cam);
      K.eyebrowRun(t, S.eye, 7.9);
      rise(t, S.ta, [8, 8.25, 8.5, 8.75], 11.72, { exit: 0.25 });
      rise(t, S.tb, [12, 12.25, 12.5, 12.75]);
      K.textRun(t, S.ba, 9.25, 11.7);
      K.textRun(t, S.bb, 13);
      const rl = sp(t, 8.6, 'default');
      put(S.rail, { sx: rl, o: rl > 0.002 ? 1 : 0 });
      S.days.forEach((d, i) => K.eyebrowRun(t, d, 9 + i * 0.25));
      K.eyebrowRun(t, S.today, 11);
      S.ticks.forEach((tk, n) => {
        const p = spHit(t, 9 + n * 0.25, 'snappy');
        const caught = (CAUGHT_PR.includes(n) && spHit(t, 'pr', 'snappy')) || (CAUGHT_SCAN.includes(n) && spHit(t, 13.1, 'snappy')) || 0;
        const tgt = n === TARGET ? spHit(t, 15.5, 'snappy') : 0;
        const missed = !CAUGHT_PR.includes(n) && !CAUGHT_SCAN.includes(n);
        const pulse = missed ? Math.max(...[15, 15.5].map((x) => (t > bt(x) ? Math.exp(-(t - bt(x)) * 7) : 0))) : 0;
        const a = clamp(0.16 + 0.84 * Math.max(caught, tgt));
        const col = pulse > 0.02 ? `rgba(194,69,45,${Math.max(a, 0.25 + 0.75 * pulse).toFixed(3)})` : `rgba(28,18,16,${a.toFixed(3)})`;
        put(tk, { o: p > 0.002 ? 1 : 0, sy: p, css: { background: tgt > 0.01 ? `rgba(28,18,16,${a.toFixed(3)})` : col } });
      });
      const pp = spHit(t, 'pr', 'snappy'), sc = spHit(t, 'scanner', 'snappy');
      put(S.prPill, { o: pp > 0.002 ? 1 : 0, s: 0.8 + 0.2 * pp });
      put(S.scPill, { o: sc > 0.002 ? 1 : 0, s: 0.8 + 0.2 * sc });
      put(S.brk, { o: sc > 0.002 ? 1 : 0, s: 1.35 - 0.35 * sc });
      const cn = spHit(t, 'count', 'snappy');
      put(S.count, { o: cn > 0.002 ? 1 : 0, s: 0.85 + 0.15 * cn });
      // grow: ink block from the tick to full frame (in stage px; the camera moves underneath it)
      // grow: an ink block starts exactly on the target tick (page → stage through the camera) and fills the frame
      const gy = ease.inOut(seg(t, 16.25, 16.95)), gx = ease.expoIn(seg(t, 16.95, 17.85));
      const tx = (tickX(TARGET) - 6) * cam.s + cam.x, ty = TL_Y * cam.s + cam.y;
      put(S.grow, { o: gy > 0.001 ? 1 : 0, x: lerp(tx, -20, gx), y: lerp(ty, -20, gy), sx: lerp(12 * cam.s, W + 40, gx), sy: lerp(100 * cam.s, H + 40, gy) });
    },
  });

  // ------------------------------------------------------------------ 3 · flaw: CI passed, the flaw shipped (b18 → b32)
  // The planted defect: the docstring promises "total refunds never exceed the payment"; the check compares one refund.
  const CODE = [
    ['', '@app.post("/refunds", status_code=201)'],
    ['', 'def create_refund(body: RefundIn, customer, store):'],
    ['i', '    """Refund part or all of a payment the customer owns.'],
    ['i', ''],
    ['i', '    Total refunds for a payment must never exceed'],
    ['i', '    the payment\'s original amount.'],
    ['i', '    """'],
    ['', '    p = store.payments.get(body.payment_id)'],
    ['', '    if p is None:'],
    ['', '        raise HTTPException(404, "not found")'],
    ['', '    require_owner(p.customer_id, customer)'],
    ['x', '    if body.amount > p.amount:'],
    ['x', '        raise HTTPException(422, "refund exceeds payment amount")'],
  ];
  const LH = 40, CODE_Y = 350, CODE_X = PAD, CODE_W = 1080;
  scene({
    name: 'flaw', from: 'flaw', to: 'ari',
    build(root, S) {
      S.bg = K.ink(root);
      S.cam = reg(el('div', { class: 'abs', style: `width:${W}px;height:${H}px` }, root));
      S.stack = reg(el('div', { class: 'abs', style: `width:${W}px;height:${H}px;transform-origin:${W / 2}px ${H / 2}px` }, S.cam));
      // the commit, rebuilt from the demo console header (frontend/app/demo/[org]/[repo]/commit)
      S.commit = reg(el('div', { class: 'abs', style: `left:${PAD}px;top:120px;width:1640px;height:170px;border-radius:20px;background:#2b1d19;box-shadow:0 0 0 1px rgba(255,255,255,.08);transform-origin:50% 0;color:#fff` }, S.stack,
        `<span style="position:absolute;left:34px;top:40px;width:72px;height:72px;border-radius:50%;background:var(--accent);display:grid;place-items:center;font:600 26px UI">PN</span>` +
        `<span style="position:absolute;left:136px;top:30px;font:600 52px UI;letter-spacing:-.02em">feat(refunds): allow partial refunds</span>` +
        `<span style="position:absolute;left:138px;top:104px;font:400 26px Mono;color:rgba(255,255,255,.5)">priya-natarajan · pushed 2 hours ago · main</span>` +
        `<span style="position:absolute;right:300px;top:58px;font:500 32px Mono"><span style="color:var(--ok-dark)">+88</span> <span style="color:#ff8a78">−19</span></span>` +
        `<span style="position:absolute;right:34px;top:50px;font:500 28px Mono;color:var(--ok-dark);background:rgba(79,191,135,.12);padding:12px 18px;border-radius:10px">✓ CI passing</span>`), { o: 0 });
      S.code = reg(el('div', { class: 'abs', style: `left:${CODE_X}px;top:${CODE_Y}px;width:${CODE_W}px;height:${CODE.length * LH + 56}px;border-radius:20px;background:#211613;box-shadow:0 0 0 1px rgba(255,255,255,.07)` }, S.stack), { o: 0 });
      S.hiI = reg(el('div', { class: 'abs', style: `left:0;top:${28 + 4 * LH}px;width:${CODE_W}px;height:${2 * LH}px;background:rgba(79,191,135,.13);border-left:6px solid var(--ok-dark);transform-origin:0 50%` }, S.code), { o: 0 });
      S.hiX = reg(el('div', { class: 'abs', style: `left:0;top:${28 + 11 * LH}px;width:${CODE_W}px;height:${2 * LH}px;background:rgba(224,104,74,.18);border-left:6px solid var(--ember);transform-origin:0 50%` }, S.code), { o: 0 });
      S.lines = CODE.map(([k, s], i) => reg(el('div', { class: 'abs mono', style: `left:44px;top:${28 + i * LH}px;font-size:26px;line-height:${LH}px;white-space:pre;color:${k === 'i' ? 'rgba(255,255,255,.55)' : 'rgba(255,255,255,.86)'}` }, S.code, s.replace(/</g, '&lt;') || ' '), { o: 0 }));
      S.tagI = reg(el('div', { class: 'abs eyebrow', style: `left:${CODE_W - 200}px;top:${28 + 4 * LH + 18}px;color:var(--ok-dark);font-size:22px` }, S.code, 'The intent'), { o: 0 });
      S.tagX = reg(el('div', { class: 'abs eyebrow', style: `left:600px;top:${28 + 11 * LH + 7}px;color:var(--ember);font-size:22px` }, S.code, 'Checks one refund, not the total'), { o: 0 });
      // the exploit, as Probe ran it in the demo: two 60.00 refunds on a 100.00 payment both succeed
      const MX = PAD + CODE_W + 40, MW = 1780 - MX;
      S.math = reg(el('div', { class: 'abs', style: `left:${MX}px;top:${CODE_Y}px;width:${MW}px;height:${CODE.length * LH + 56}px;border-radius:20px;background:#2b1d19;box-shadow:0 0 0 1px rgba(255,255,255,.08);color:#fff` }, S.stack), { o: 0 });
      el('div', { class: 'abs eyebrow', style: 'left:34px;top:30px;color:rgba(255,255,255,.45);font-size:22px' }, S.math, 'POST /refunds · pay_1001');
      const row = (y, a, bb, c, cc = 'rgba(255,255,255,.55)') => reg(el('div', { class: 'abs mono', style: `left:34px;top:${y}px;width:${MW - 68}px;display:flex;font-size:30px;line-height:40px` }, S.math,
        `<span style="flex:1;color:rgba(255,255,255,.7)">${a}</span><span style="width:170px;text-align:right">${bb}</span><span style="width:110px;text-align:right;color:${cc}">${c}</span>`), { o: 0 });
      S.r0 = row(96, 'Payment', '100.00', '');
      S.r1 = row(160, 'Refund', '60.00', '201 ✓', 'var(--ok-dark)');
      S.r2 = row(224, 'Refund', '60.00', '201 ✓', 'var(--ok-dark)');
      S.r3 = row(314, 'Refunded', '120.00', '✕', '#ff8a78');
      S.rule = reg(el('div', { class: 'abs', style: `left:34px;top:290px;width:${MW - 68}px;height:2px;background:rgba(255,255,255,.14);transform-origin:0 50%` }, S.math), { o: 0 });
      S.barW = MW - 68 - 70;
      S.bar = reg(el('div', { class: 'abs', style: `left:34px;top:410px;width:${S.barW}px;height:22px;border-radius:11px;background:rgba(255,255,255,.08)` }, S.math), { o: 0 });
      S.fill = reg(el('div', { class: 'abs', style: `left:34px;top:410px;width:${S.barW}px;height:22px;border-radius:11px;background:var(--ok-dark);transform-origin:0 50%` }, S.math), { o: 0 });
      S.over = reg(el('div', { class: 'abs', style: `left:${34 + S.barW}px;top:410px;width:${S.barW * 0.2}px;height:22px;border-radius:0 11px 11px 0;background:#ff6a52;transform-origin:0 50%` }, S.math), { o: 0 });
      S.cap = reg(el('div', { class: 'abs', style: `left:${34 + S.barW - 2}px;top:396px;width:4px;height:50px;background:#fff` }, S.math), { o: 0 });
      S.capL = reg(el('div', { class: 'abs eyebrow', style: `left:${34 + S.barW - 120}px;top:458px;color:rgba(255,255,255,.55);font-size:22px` }, S.math, 'Payment'), { o: 0 });
      // the verdict, over everything
      S.v1 = K.head(S.cam, 'CI PASSED.', PAD, 340, 150, { color: '#fff' });
      S.v2 = K.head(S.cam, 'THE FLAW SHIPPED.', PAD, 500, 150, { color: 'var(--ember)' });
      S.q1 = K.head(S.cam, 'WHO CHECKS', PAD, 340, 150, { color: '#fff' });
      S.q2 = K.head(S.cam, 'EVERY CHANGE?', PAD, 500, 150, { color: 'var(--ember)' });
      S.ctx = canvas(root);
      S.lone = K.path([{ x: -80, y: 820 }, { x: 420, y: 820 }, { x: 760, y: 800 }, { x: 980, y: 804 }]);
    },
    run(t, b, S) {
      K.inkRun(t, S.bg, 0.1 + 0.3 * sp(t, 'total', 'heavy') - 0.4 * sp(t, 29, 'heavy'), 120);
      put(S.cam, K.aim(W / 2, H / 2, 1.035 - 0.035 * ease.out(seg(t, 18, 23))));
      const c = sp(t, 'flaw', 'default');
      put(S.commit, { o: c > 0.002 ? 1 : 0, s: 0.9 + 0.1 * c, y: -40 * (1 - c) });
      const cd = sp(t, 18.75, 'default');
      put(S.code, { o: cd > 0.002 ? 1 : 0, y: 60 * (1 - cd) });
      S.lines.forEach((ln, i) => { const p = spHit(t, 19 + i * 0.0625, 'snappy'); put(ln, { o: p > 0.002 ? 1 : 0, x: -20 * (1 - p) }); });
      const hi = spHit(t, 'pay', 'snappy'), hx = spHit(t, 22.5, 'snappy');
      put(S.hiI, { o: hi > 0.002 ? 1 : 0, sx: hi });
      put(S.tagI, { o: clamp(hi * 1.5), x: 20 * (1 - hi) });
      put(S.hiX, { o: hx > 0.002 ? 1 : 0, sx: hx });
      put(S.tagX, { o: clamp(hx * 1.5), x: 20 * (1 - hx) });
      const m = sp(t, 19.5, 'default');
      put(S.math, { o: m > 0.002 ? 1 : 0, y: 60 * (1 - m) });
      [[S.r0, 20.5], [S.r1, 21.5], [S.r2, 22], [S.r3, 'total']].forEach(([r, at]) => { const p = spHit(t, at, 'snappy'); put(r, { o: p > 0.002 ? 1 : 0, x: -24 * (1 - p) }); });
      const rl = sp(t, 22.6, 'snappy');
      put(S.rule, { o: rl > 0.002 ? 1 : 0, sx: rl });
      const bb = sp(t, 20.6, 'default');
      put(S.bar, { o: bb > 0.002 ? 1 : 0 }); put(S.cap, { o: bb > 0.002 ? 1 : 0 }); put(S.capL, { o: clamp(bb * 1.3) });
      const F = 0.6 * spHit(t, 21.5, 'snappy') + 0.6 * spHit(t, 22, 'snappy');   // refunded / payment
      put(S.fill, { o: F > 0.002 ? 1 : 0, sx: Math.min(1, F), css: { background: F > 1.001 ? '#ff6a52' : 'var(--ok-dark)' } });
      put(S.over, { o: F > 1.001 ? 1 : 0, sx: clamp((F - 1) / 0.2) });
      // verdict over the receding evidence; then the question; then a lone scout in the dark
      const back = sp(t, 23.85, 'heavy'), gone = sp(t, 26.3, 'default');
      put(S.stack, { o: 1 - gone, s: 1 - 0.08 * back - 0.1 * gone, filter: back > 0.01 ? `brightness(${(1 - 0.72 * back).toFixed(3)}) blur(${(5 * back).toFixed(2)}px)` : 'none' });
      rise(t, S.v1, [24, 24.25], 26.85, { exit: 0.3 });
      rise(t, S.v2, [25, 25.25, 25.5], 26.85, { exit: 0.3 });
      rise(t, S.q1, [27, 27.25], 31.75, { exit: 0.25 });
      rise(t, S.q2, [27.5, 27.75], 31.75, { exit: 0.25 });
      const g = S.ctx; g.clearRect(0, 0, W, H);
      const walk = seg(t, 28.4, 31), d = S.lone.length * ease.out(walk);
      if (walk > 0) {
        g.save(); g.lineWidth = 1.8; g.setLineDash([2, 9]); g.lineDashOffset = -(t - bt(28.4)) * 22; g.strokeStyle = K.TRAILC; K.strokeSpan(g, S.lone, 0, d); g.restore();
        const stop = t > bt(31);
        K.antOn(g, S.lone, Math.max(0.1, d), 1, { t: stop ? bt(31) + (t - bt(31)) * 0.15 : t, scale: 4.6, color: K.SCOUT, alpha: 1, phase: 0.5 });
      }
    },
  });
})();
