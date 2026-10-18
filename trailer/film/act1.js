// INTRO: software changes every day; most changes never get fully checked; meet Ari; Ari works in three parts.
// Also the two shared scene makers: the three-part menu (shown before each chapter) and the chapter title card.
(() => {
  const { W, H, el, reg, put, scene, canvas, sp, spHit, trk, seg, clamp, lerp, ease, bt, beatOf, rectOf } = C;
  const { rise } = TYPE;
  const PAD = K.PAD;
  const full = (root) => reg(el('div', { class: 'abs', style: `width:${W}px;height:${H}px` }, root));

  // Real code (examples/payments-lite/target/payments_lite/app.py) as a quiet texture.
  const WALL = ['@app.post("/payments", status_code=201)', 'def create_payment(body: PaymentIn, customer, store) -> PaymentOut:',
    '    p = Payment(store.next_id("pay"), customer.id, body.amount, body.currency)', '    store.payments[p.id] = p', '    return payment_out(store, p)', '',
    '@app.post("/refunds", status_code=201)', 'def create_refund(body: RefundIn, customer, store) -> RefundOut:',
    '    """Refund part or all of a payment the customer owns.', '', '    Total refunds for a payment must never exceed', '    the payment\'s original amount.', '    """',
    '    p = store.payments.get(body.payment_id)', '    if p is None:', '        raise HTTPException(404, "not found")', '    require_owner(p.customer_id, customer)',
    '    if body.amount > p.amount:', '        raise HTTPException(422, "refund exceeds payment amount")', '    r = Refund(store.next_id("ref"), p.id, body.amount)', '',
    '@app.get("/refunds/{refund_id}")', 'def get_refund(refund_id: str, customer, store) -> RefundOut:', '    r = store.refunds.get(refund_id)', '    if r is None:',
    '        raise HTTPException(404, "not found")', '    require_owner(r.customer_id, customer)', '', 'def require_owner(owner_id: str, customer: Customer) -> None:',
    '    if owner_id != customer.id:', '        raise HTTPException(403, "forbidden")'];
  const COMMITS = [['PN', 'docs: document the require_owner convention', 'priya-natarajan · 3 days ago'], ['AK', 'test: cover currency validation edge cases', 'akshar-koth · 2 days ago'],
    ['MO', 'refactor(store): extract refunds_for helper', 'mina-okafor · 1 day ago'], ['JP', 'feat(search): filter payments by description', 'jules-park · 22 hours ago'],
    ['DS', 'fix(customers): return 404 for unknown customer ids', 'devon-shah · 7 hours ago'], ['SL', 'chore(deps): bump pydantic to 2.12.4', 'sam-lindqvist · 4 hours ago'],
    ['PN', 'feat(refunds): allow partial refunds', 'priya-natarajan · 2 hours ago'], ['AK', 'feat(payments): add GET /payments/{payment_id} lookup', 'akshar-koth · 14 min ago']];
  const ARRIVE = [2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5];

  // ------------------------------------------------------------------ open: software changes every day (b0 → b12)
  scene({
    name: 'open', from: 'open', to: 'week',
    build(root, S) {
      S.bg = K.ink(root);
      S.cam = full(root);
      S.wall = reg(el('div', { class: 'abs mono', style: `left:${PAD}px;top:60px;font-size:24px;line-height:38px;color:rgba(255,255,255,.075);white-space:pre` }, S.cam));
      WALL.forEach((s) => el('div', {}, S.wall, s.replace(/</g, '&lt;') || ' '));
      S.l1 = K.head(S.cam, 'SOFTWARE CHANGES', PAD, 310, 110, { color: '#fff' });
      S.l2 = K.head(S.cam, 'EVERY DAY.', PAD, 428, 110, { color: 'var(--ember)' });
      S.sub = K.say(S.cam, ['Every update can break something,', 'or open a door to attackers.'], PAD, 640, { size: 44, color: 'rgba(255,255,255,.85)', weight: 500 });
      S.feed = reg(el('div', { class: 'abs', style: 'left:1236px;top:0px;width:720px;height:1080px' }, S.cam));
      S.cards = COMMITS.map(([who, msg, meta], i) => reg(el('div', { class: 'abs', style: `left:0;top:802px;width:720px;height:112px;border-radius:16px;background:#2b1d19;box-shadow:0 0 0 1px rgba(255,255,255,.07);display:flex;align-items:center;gap:22px;padding:0 26px;box-sizing:border-box;color:#fff` }, S.feed,
        `<span style="flex:none;width:52px;height:52px;border-radius:50%;background:${i === 6 ? 'var(--accent)' : '#4a2c25'};display:grid;place-items:center;font:600 20px UI">${who}</span>` +
        `<span style="flex:1;min-width:0"><span style="display:block;font:500 29px UI;letter-spacing:-.01em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${msg}</span>` +
        `<span style="display:block;margin-top:6px;font:400 21px Mono;color:rgba(255,255,255,.5)">${meta} · main</span></span>` +
        `<span style="flex:none;width:40px;height:40px;border-radius:50%;background:rgba(79,191,135,.14);color:var(--ok-dark);display:grid;place-items:center;font:600 22px UI;margin-right:48px">✓</span>`), { o: 0 }));
    },
    run(t, b, S) {
      K.inkRun(t, S.bg, 0.55, 122);
      put(S.cam, K.aim(W / 2, H / 2, 1 + 0.045 * ease.inOut(seg(t, -1, 12))));
      put(S.wall, { y: -420 * seg(t, -2, 13) });
      rise(t, S.l1, [-0.4, 0.5]);
      rise(t, S.l2, [1.5, 2]);
      K.sayRun(t, S.sub, 4.5);
      const n = trk(t, [[0, 0], ...ARRIVE.map((a, k) => [a, k + 1, 'snappy'])]);
      S.cards.forEach((c, i) => { const p = spHit(t, ARRIVE[i], 'snappy'); put(c, { o: p > 0.002 ? 1 : 0, y: -(n - 1 - i) * 128 + 160 * (1 - p), s: 0.96 + 0.04 * p }); });
    },
  });

  // ------------------------------------------------------------------ week: most changes never get fully checked (b12 → b30)
  const TICK_X = [4, 11, 17, 26, 31, 39, 47, 55, 62, 70, 79, 88], TARGET = 8;
  const TL_X = PAD, TL_W = 1640, TL_Y = 700, tickX = (n) => TL_X + (TICK_X[n] / 100) * TL_W;
  scene({
    name: 'week', from: 'week', to: 'meet',
    build(root, S) {
      S.bg = K.paper(root, true);
      S.cam = full(root);
      S.eye = K.eyebrow(S.cam, 'The problem', PAD, 120);
      S.s1 = K.say(S.cam, ['Code reviews only see', 'the lines that changed.'], PAD, 186, { size: 64, color: 'var(--ink)' });
      S.s2 = K.say(S.cam, ['Security scans only check', 'once in a while.'], PAD, 186, { size: 64, color: 'var(--ink)' });
      S.s3 = K.say(S.cam, ['So most changes are never', 'fully checked.'], PAD, 186, { size: 64, color: 'var(--ink)', hl: ['never', 'fully', 'checked.'], hlc: 'var(--accent)' });
      S.rail = reg(el('div', { class: 'abs', style: `left:${TL_X}px;top:${TL_Y + 48}px;width:${TL_W}px;height:3px;background:var(--line);transform-origin:0 50%` }, S.cam));
      S.days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'].map((d, i) => reg(el('div', { class: 'abs eyebrow', style: `left:${TL_X + i * (TL_W / 4) - (i === 4 ? 40 : 0)}px;top:${TL_Y + 128}px;color:var(--faint);font-size:24px` }, S.cam, d), { o: 0 }));
      S.ticks = TICK_X.map((_, n) => reg(el('div', { class: 'abs', style: `left:${tickX(n) - 6}px;top:${TL_Y}px;width:12px;height:100px;border-radius:6px;background:var(--ink);transform-origin:50% 100%` }, S.cam), { o: 0 }));
      const pill = (txt, x) => reg(el('div', { class: 'abs eyebrow', style: `left:${x}px;top:${TL_Y - 76}px;padding:8px 14px;border-radius:8px;background:var(--ink);color:#fff;font-size:24px;transform-origin:20px 100%` }, S.cam, txt), { o: 0 });
      S.pr = pill('Code review', tickX(1) - 20);
      S.sc = pill('Scan', tickX(6) - 20);
      S.count = reg(el('div', { class: 'abs eyebrow', style: `left:${PAD}px;top:${TL_Y - 170}px;padding:10px 16px;border-radius:8px;background:var(--accent);color:#fff;font-size:28px;transform-origin:0 100%` }, S.cam, 'Only 3 of 12 changes checked'), { o: 0 });
      S.grow = reg(el('div', { class: 'abs', style: 'width:1px;height:1px;background:var(--ink)' }, root), { o: 0 });
    },
    run(t, b, S) {
      const dive = ease.expoIn(seg(t, 28, 29.9));
      const cam = K.aim(lerp(W / 2, tickX(TARGET), dive), lerp(H / 2, TL_Y + 50, dive), 1 + 0.05 * ease.out(seg(t, 12, 28)) + 1.4 * dive);
      put(S.cam, cam);
      K.eyebrowRun(t, S.eye, 11.9);
      K.sayRun(t, S.s1, 12, 17.6);
      K.sayRun(t, S.s2, 18, 23.6);
      K.sayRun(t, S.s3, 24);
      const rl = sp(t, 12.5, 'default'); put(S.rail, { sx: rl, o: rl > 0.002 ? 1 : 0 });
      S.days.forEach((d, i) => K.eyebrowRun(t, d, 13 + i * 0.25));
      S.ticks.forEach((tk, n) => {
        const p = spHit(t, 13 + n * 0.25, 'snappy');
        const caught = (n === 1 && spHit(t, 16, 'snappy')) || ((n === 6 || n === 7) && spHit(t, 19.5, 'snappy')) || 0;
        const tgt = n === TARGET ? spHit(t, 27.5, 'snappy') : 0, missed = ![1, 6, 7].includes(n);
        const pulse = missed ? Math.max(...[26, 26.5].map((x) => (t > bt(x) ? Math.exp(-(t - bt(x)) * 7) : 0))) : 0;
        const a = clamp(0.16 + 0.84 * Math.max(caught, tgt));
        put(tk, { o: p > 0.002 ? 1 : 0, sy: p, css: { background: pulse > 0.02 && tgt < 0.01 ? `rgba(194,69,45,${Math.max(a, 0.25 + 0.75 * pulse).toFixed(3)})` : `rgba(28,18,16,${a.toFixed(3)})` } });
      });
      const pp = spHit(t, 16, 'snappy'), sc = spHit(t, 19.5, 'snappy'), cn = spHit(t, 25, 'snappy');
      put(S.pr, { o: pp > 0.002 ? 1 : 0, s: 0.8 + 0.2 * pp });
      put(S.sc, { o: sc > 0.002 ? 1 : 0, s: 0.8 + 0.2 * sc });
      put(S.count, { o: cn > 0.002 ? 1 : 0, s: 0.85 + 0.15 * cn });
      const gy = ease.inOut(seg(t, 28.25, 28.95)), gx = ease.expoIn(seg(t, 28.95, 29.85));
      const tx = (tickX(TARGET) - 6) * cam.s + cam.x, ty = TL_Y * cam.s + cam.y;
      put(S.grow, { o: gy > 0.001 ? 1 : 0, x: lerp(tx, -20, gx), y: lerp(ty, -20, gy), sx: lerp(12 * cam.s, W + 40, gx), sy: lerp(100 * cam.s, H + 40, gy) });
    },
  });

  // ------------------------------------------------------------------ meet: the colony and the lockup (b30 → b44)
  const TRS = K.TRAILS.map((c) => K.trail(c, W, H));
  const COL = K.colony({ trails: TRS, nests: K.NESTS, n: 36, first: 10, seed: 146, speed: 1 });
  scene({
    name: 'meet', from: 'meet', to: 'menu1',
    build(root, S) {
      S.bg = K.ink(root);
      S.ctx = canvas(root);
      S.cam = full(root);
      S.mark = K.mark(S.cam, 176, '#fff');
      Object.assign(S.mark.style, { left: PAD + 'px', top: '300px', transformOrigin: '50% 100%' });
      S.word = K.head(S.cam, 'A R I', PAD + 280, 284, 250, { color: '#fff' });
      Object.assign(S.word.el.style, { fontFamily: 'Wordmark', letterSpacing: '0.08em', lineHeight: '1' });
      [...S.word.el.childNodes].filter((n) => n.nodeType === 3).forEach((n) => n.remove());
      S.sub = K.say(S.cam, ['An AI engineering and security team', 'that checks every change to your code.'], PAD, 590, { size: 56, hl: ['every', 'change'] });
      S.lone = K.path([{ x: -80, y: 860 }, { x: 600, y: 860 }, { x: 900, y: 845 }]);
    },
    run(t, b, S) {
      K.inkRun(t, S.bg, 0.45 + 0.55 * sp(t, 32, 'heavy'), 108);
      const g = S.ctx; g.clearRect(0, 0, W, H);
      if (b >= 31.8) K.colonyDraw(g, COL, t - bt(32) + 0.25, { scale: 1.7 });
      else {                                                         // a lone scout comes first
        const d = S.lone.length * ease.out(seg(t, 30, 31.4));
        g.save(); g.lineWidth = 1.8; g.setLineDash([2, 9]); g.strokeStyle = K.TRAILC; K.strokeSpan(g, S.lone, 0, d); g.restore();
        K.antOn(g, S.lone, Math.max(0.1, d), 1, { t: Math.min(t, bt(31.4)), scale: 4.6, color: K.SCOUT });
      }
      put(S.cam, K.aim(W / 2, H / 2, 1 + 0.05 * ease.inOut(seg(t, 32, 44))));
      const m = spHit(t, 32, 'playful');
      put(S.mark, { o: m > 0.002 ? 1 : 0, s: 0.55 + 0.45 * m, r: -10 * (1 - m) });
      rise(t, S.word, [32, 32.25, 32.5], 43.6, { exit: 0.3 });
      K.sayRun(t, S.sub, 35, 43.6);
    },
  });

  // ------------------------------------------------------------------ the three-part menu, shown before each chapter
  const PARTS = [['01', 'review', ['THE CODE', 'REVIEWER'], 'Does your code do what it is supposed to?'],
    ['02', 'team', ['THE SECURITY', 'TEAM'], 'Can someone break in?'],
    ['03', 'lab', ['DEFENSE', 'LAB'], 'Can we stop attacks after launch?']];
  const CW = 520, CH = 560, CX = (i) => PAD + i * 560, CY = 330;
  K.menu = (name, from, to, active, intro) => scene({
    name, from, to,
    build(root, S) {
      S.bg = K.ink(root);
      S.cam = full(root);
      S.say = K.say(S.cam, intro ? ['Ari works in three parts.'] : [['', 'Part two.', 'Part three.'][active]], PAD, 150, { size: 64 });
      S.cards = PARTS.map(([n, icon, title, q], i) => reg(el('div', { class: 'abs', style: `left:${CX(i)}px;top:${CY}px;width:${CW}px;height:${CH}px;border-radius:24px;background:#2b1d19;box-shadow:0 0 0 1px rgba(255,255,255,.1);color:#fff;transform-origin:50% 100%` }, S.cam,
        `<div class="eyebrow" style="position:absolute;left:36px;top:32px;color:var(--ember);font-size:26px">${n}</div>` +
        `<div style="position:absolute;left:36px;top:92px;width:96px;height:96px;color:#fff">${K.ICON[icon]}</div>` +
        `<div class="display" style="position:absolute;left:36px;top:236px;font-size:60px">${title.join('<br>')}</div>` +
        `<div style="position:absolute;left:36px;top:392px;width:440px;font:500 36px UI;line-height:1.25;color:rgba(255,255,255,.8);letter-spacing:-.01em">${q}</div>` +
        (i < active ? '<div class="eyebrow" style="position:absolute;right:30px;top:30px;padding:6px 12px;border-radius:8px;background:rgba(79,191,135,.15);color:var(--ok-dark);font-size:22px">✓ Covered</div>' : '')), { o: 0 }));
      S.grow = reg(el('div', { class: 'abs', style: `width:${W}px;height:${H}px;background:#2b1d19` }, root), { o: 0 });
    },
    run(t, b, S) {
      const f = beatOf(from), tt = beatOf(to);
      K.inkRun(t, S.bg, 0.5, 115);
      put(S.cam, K.aim(W / 2, H / 2, 1 + 0.03 * ease.inOut(seg(t, f, tt))));
      K.sayRun(t, S.say, f + 0.5, tt - 2.4);
      const deal = intro ? [f + 2.5, f + 4, f + 5.5] : [f, f, f];
      const lit = f + (intro ? 12.5 : 3);
      S.cards.forEach((c, i) => {
        const p = intro ? spHit(t, deal[i], 'snappy') : 1;
        const on = i === active ? spHit(t, lit, 'snappy') : 0, dim = i !== active ? sp(t, lit, 'default') : 0;
        put(c, { o: p > 0.002 ? 1 - 0.55 * dim : 0, y: 120 * (1 - p), s: (0.92 + 0.08 * p) * (1 + 0.04 * on),
          css: { boxShadow: on > 0.01 ? `0 0 0 ${(3 * on).toFixed(2)}px var(--ember), 0 40px 90px -30px rgba(0,0,0,.6)` : '0 0 0 1px rgba(255,255,255,.1)' } });
      });
    },
    after(t, b, S) {
      const tt = beatOf(to), g = ease.expoIn(seg(t, tt - 1.8, tt - 0.05));
      if (g <= 0.001) { put(S.grow, { o: 0 }); return; }
      const r = rectOf(S.cards[active]), k = (v) => lerp(v, -2, g).toFixed(2);
      put(S.grow, { o: 1, clip: `inset(${k(r.y)}px ${k(W - r.x - r.w)}px ${k(H - r.y - r.h)}px ${k(r.x)}px round ${(24 * (1 - g)).toFixed(1)}px)` });
    },
  });
  K.menu('menu1', 'menu1', 'c1', 0, true);

  // ------------------------------------------------------------------ chapter title card
  K.chapter = (name, from, to, num, title, q) => scene({
    name, from, to,
    build(root, S) {
      S.bg = K.ink(root); root.style.background = '#2b1d19';
      S.cam = full(root);
      S.num = K.head(S.cam, num, PAD, 170, 240, { color: 'var(--ember)' });
      S.t = K.head(S.cam, title, PAD, 430, 140, { color: '#fff' });
      S.q = K.say(S.cam, [q], PAD, 640, { size: 60, color: 'rgba(255,255,255,.88)', weight: 500 });
    },
    run(t, b, S) {
      const f = beatOf(from), tt = beatOf(to);
      K.inkRun(t, S.bg, 0.7, 112);
      put(S.cam, K.aim(W / 2, H / 2, 1 + 0.04 * ease.inOut(seg(t, f, tt))));
      rise(t, S.num, [f - 0.1], tt - 0.5, { exit: 0.3 });
      rise(t, S.t, S.t.words.map((_, i) => f + 0.4 + i * 0.25), tt - 0.5, { exit: 0.3 });
      K.sayRun(t, S.q, f + 2, tt - 0.5);
    },
  });
  K.chapter('c1title', 'c1', 'c1_intent', '01', 'THE CODE REVIEWER', 'Does your code do what it is supposed to?');
})();
