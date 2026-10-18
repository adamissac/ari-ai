// OUTRO: three parts, one loop; no AI output counts as proof, including ours; the lockup and the address.
(() => {
  const { W, H, el, reg, put, scene, canvas, sp, spHit, seg, clamp, lerp, ease, bt } = C;
  const { rise } = TYPE;
  const PAD = K.PAD;
  const full = (root) => reg(el('div', { class: 'abs', style: `width:${W}px;height:${H}px` }, root));

  // ------------------------------------------------------------------ one loop (b420 → b432)
  const RC = { x: 1390, y: 590 }, RR = 290;
  scene({
    name: 'loop', from: 'loop', to: 'proof',
    build(root, S) {
      S.bg = K.ink(root);
      S.cam = full(root);
      S.ctx = canvas(S.cam);
      S.s1 = K.say(S.cam, ['Three parts.', 'One loop.'], PAD, 330, { size: 96, hl: ['One', 'loop.'] });
      S.s2 = K.say(S.cam, ['Every change is understood, tested,', 'fixed with proof, and watched.'], PAD, 620, { size: 40, color: 'rgba(255,255,255,.82)', weight: 500 });
      S.ring = K.trail((a) => ({ x: Math.cos(a - Math.PI / 2), y: Math.sin(a - Math.PI / 2) }), RR, RR, 600, RC.x, RC.y);
      S.pins = K.LOOP.map(() => reg(el('div', { class: 'abs' }, S.cam)));
      S.chips = K.LOOP.map((s, i) => { const c = K.chip(S.pins[i], i + 1, s, 22); c.style.transform = 'translate(-50%, -50%)'; return c; });
    },
    run(t, b, S) {
      K.inkRun(t, S.bg, 0.5, 112, 72);
      put(S.cam, K.aim(W / 2, H / 2, 1 + 0.04 * ease.inOut(seg(t, 420, 432))));
      K.sayRun(t, S.s1, 420.5, 431.4); K.sayRun(t, S.s2, 422.5, 431.4);
      const g = S.ctx; g.clearRect(0, 0, W, H);
      const rp = ease.inOut(seg(t, 420.5, 422.5));
      g.strokeStyle = 'rgba(255,255,255,.12)'; g.lineWidth = 2; K.strokeSpan(g, S.ring, 0, S.ring.length * rp, 4);
      const lit = b < 423 ? -1 : Math.floor((b - 423) * 2) % 7;
      S.chips.forEach((c, i) => {
        const a = (i / 7) * Math.PI * 2 - Math.PI / 2, p = spHit(t, 421 + i * 0.25, 'snappy');
        put(S.pins[i], { x: RC.x + Math.cos(a) * RR, y: RC.y + Math.sin(a) * RR, s: 0.8 + 0.2 * p });
        put(c, { o: p > 0.002 ? 1 : 0, css: { background: i === lit ? 'var(--accent)' : 'rgba(43,29,25,.96)', color: i === lit ? '#fff' : 'rgba(255,255,255,.88)', boxShadow: '0 0 0 1px rgba(255,255,255,.1)' } });
      });
      if (b > 422) { const tc = t - bt(422); for (let k = 0; k < 14; k++) K.antOn(g, S.ring, (k / 14) * S.ring.length + tc * 150, 1, { t: tc, lane: ((k * 7) % 5 - 2) * 4, seed: (k * 0.37) % 1, phase: k, scale: 1.7, alpha: clamp(tc * 2 - k * 0.08), color: k === 0 ? K.SCOUT : K.ANT }); }
    },
  });

  // ------------------------------------------------------------------ proof (b432 → b444)
  scene({
    name: 'proof', from: 'proof', to: 'end',
    build(root, S) {
      S.bg = K.ink(root);
      S.cam = full(root);
      S.l1 = K.head(S.cam, 'NO AI OUTPUT COUNTS', PAD, 330, 140, { color: '#fff' });
      S.l2 = K.head(S.cam, 'AS PROOF.', PAD, 480, 140, { color: '#fff' });
      S.l3 = K.head(S.cam, 'INCLUDING OURS.', PAD, 400, 200, { color: 'var(--ember)' });
      S.sub = K.say(S.cam, ['Every claim in Ari links to the', 'evidence behind it.'], PAD, 690, { size: 50 });
    },
    run(t, b, S) {
      K.inkRun(t, S.bg, 0.3 + 0.5 * ease.expoIn(seg(t, 438, 443.5)), 116);
      put(S.cam, K.aim(W / 2, H / 2, 1 + 0.05 * ease.inOut(seg(t, 432, 444))));
      rise(t, S.l1, [432.5, 432.75, 433, 433.25], 437.6, { exit: 0.3 });
      rise(t, S.l2, [433.75, 434], 437.6, { exit: 0.3 });
      rise(t, S.l3, [438, 438.5], 443.2, { exit: 0.3 });
      K.sayRun(t, S.sub, 439.5, 443.1);
    },
  });

  // ------------------------------------------------------------------ end: the lockup and the address (b444 → b456)
  const TRS = K.TRAILS.map((c) => K.trail(c, W, H));
  const COL = K.colony({ trails: TRS, nests: K.NESTS, n: 40, first: 12, seed: 172, speed: 1 });
  scene({
    name: 'end', from: 'end', to: 'done',
    build(root, S) {
      S.bg = K.ink(root);
      S.ctx = canvas(root);
      S.cam = full(root);
      S.mark = K.mark(S.cam, 150, '#fff');
      Object.assign(S.mark.style, { left: PAD + 'px', top: '262px', transformOrigin: '50% 100%' });
      S.word = K.head(S.cam, 'A R I', PAD + 240, 248, 214, { color: '#fff' });
      Object.assign(S.word.el.style, { fontFamily: 'Wordmark', letterSpacing: '0.08em', lineHeight: '1' });
      [...S.word.el.childNodes].filter((n) => n.nodeType === 3).forEach((n) => n.remove());
      S.tag = K.head(S.cam, 'FIND THE FLAW. PROVE THE FIX.', PAD, 520, 76, { color: '#fff' });
      S.tag.words.slice(3).forEach((w) => (w.style.color = 'var(--ember)'));
      S.eye = K.eyebrow(S.cam, 'See it run', PAD + 2, 690, 'var(--ember)', 26);
      S.url = K.head(S.cam, 'ari-ai-lake.vercel.app', PAD, 734, 58, { color: '#fff', cls: 'mono' });
      S.url.el.style.letterSpacing = '-0.01em'; S.url.el.style.fontWeight = '500';
      S.rule = reg(el('div', { class: 'abs', style: `left:${PAD}px;top:824px;width:770px;height:6px;border-radius:3px;background:var(--accent);transform-origin:0 50%` }, S.cam), { o: 0 });
    },
    run(t, b, S) {
      K.inkRun(t, S.bg, 0.5 + 0.5 * sp(t, 'end', 'heavy'), 108);
      const g = S.ctx; g.clearRect(0, 0, W, H);
      K.colonyDraw(g, COL, t - bt('end') + 0.3, { scale: 1.7 });
      put(S.cam, K.aim(W / 2, H / 2, 1.0 + 0.045 * ease.inOut(seg(t, 444, 456))));
      const m = spHit(t, 'end', 'playful');
      put(S.mark, { o: m > 0.002 ? 1 : 0, s: 0.55 + 0.45 * m, r: -10 * (1 - m) });
      rise(t, S.word, [444, 444.25, 444.5]);
      rise(t, S.tag, [445, 445.12, 445.25, 445.5, 445.62, 445.75]);
      K.eyebrowRun(t, S.eye, 446);
      rise(t, S.url, [446.25]);
      const u = sp(t, 447, 'default'); put(S.rule, { o: u > 0.002 ? 1 : 0, sx: u });
    },
  });
})();
