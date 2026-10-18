// ACT 5: proof, standards, and the close. "No model output counts as proof, including ours." (frontend story.tsx)
(() => {
  const { W, H, el, reg, put, scene, canvas, sp, spHit, seg, clamp, lerp, ease, bt } = C;
  const { rise } = TYPE;
  const PAD = K.PAD;
  const full = (root) => reg(el('div', { class: 'abs', style: `width:${W}px;height:${H}px` }, root));

  // ------------------------------------------------------------------ 15 · proof: the record is checkable (b152 → b164)
  const STATS = [['01', 'Design', 7, '', 'Separate security agents, each its own tool loop with enforced permissions.'],
    ['02', 'Rule', 2, '×', 'A failing test only counts if it fails the same way twice.'],
    ['03', 'Rule', 0, '', 'The person who asks can never approve.']];
  const DEALS = [158.75, 159.25, 159.75];
  scene({
    name: 'proof', from: 'proof', to: 'standards', pre: 1,
    build(root, S) {
      S.bg = K.ink(root);
      S.cam = full(root);
      S.l1 = K.head(S.cam, 'NO MODEL OUTPUT', PAD, 330, 150, { color: '#fff' });
      S.l2 = K.head(S.cam, 'COUNTS AS PROOF.', PAD, 490, 150, { color: '#fff' });
      S.l3 = K.head(S.cam, 'INCLUDING OURS.', PAD, 400, 210, { color: 'var(--ember)' });
      S.eye = K.eyebrow(S.cam, 'Proof, not promises', PAD, 150, 'rgba(255,255,255,.6)');
      S.title = K.head(S.cam, 'THE RECORD IS CHECKABLE.', PAD, 206, 100, { color: '#fff' });
      S.cards = STATS.map(([n, tag, , , body], i) => {
        const c = reg(el('div', { class: 'abs', style: `left:${PAD + i * 556}px;top:430px;width:528px;height:400px;border-radius:20px;background:rgba(255,255,255,.05);box-shadow:0 0 0 1px rgba(255,255,255,.1);color:#fff;transform-origin:50% 100%` }, S.cam,
          `<div class="eyebrow" style="position:absolute;left:30px;top:26px;font-size:22px;color:rgba(255,255,255,.5)">${n}</div><div class="eyebrow" style="position:absolute;right:30px;top:26px;font-size:22px;color:rgba(255,255,255,.5)">${tag}</div>` +
          `<div class="mono" style="position:absolute;left:28px;top:96px;font-size:130px;font-weight:600;letter-spacing:-.04em;line-height:1"></div>` +
          `<div style="position:absolute;left:30px;top:270px;width:460px;font:400 30px UI;line-height:1.3;color:rgba(255,255,255,.74)">${body}</div>`), { o: 0 });
        c._num = reg(c.children[2]);
        return c;
      });
    },
    run(t, b, S) {
      K.inkRun(t, S.bg, 0.3 + 0.3 * sp(t, 'stats', 'heavy'), 116);
      const wp = K.wipe(t, 151, 152);
      put(S.root, { clip: wp < 1 ? C.inset(0, 100 * (1 - wp), 0, 0) : 'none' });
      put(S.cam, K.aim(W / 2, H / 2, 1 + 0.04 * ease.inOut(seg(t, 152, 164))));
      rise(t, S.l1, [152.25, 152.5, 152.75], 155.75, { exit: 0.3 });
      rise(t, S.l2, [153, 153.25, 153.5], 155.75, { exit: 0.3 });
      rise(t, S.l3, [156, 156.5], 157.8, { exit: 0.3 });
      K.eyebrowRun(t, S.eye, 157.75, 163.2);
      rise(t, S.title, [158, 158.2, 158.4, 158.6], 163.3, { exit: 0.3 });
      S.cards.forEach((c, i) => {
        const p = spHit(t, DEALS[i], 'snappy'), q = sp(t, 163.3 + i * 0.1, 'default');
        put(c, { o: p > 0.002 && q < 0.995 ? 1 : 0, y: 120 * (1 - p) - 700 * ease.expoIn(q), s: 0.92 + 0.08 * p });
        const [, , to, suf] = STATS[i];
        const txt = to ? `${K.count(t, 0, to, DEALS[i], DEALS[i] + 1)}${suf}` : 'Never'.slice(0, Math.ceil(seg(t, DEALS[i] + 0.1, DEALS[i] + 0.9) * 5));
        put(c._num, { text: txt });
      });
    },
  });

  // ------------------------------------------------------------------ 16 · standards: every finding, tagged (b164 → b172)
  const TAGS = ['CWE-840', 'MITRE ATT&CK', 'D3FEND', 'CVSS 4.0', 'NIST SP 800-61r3', 'OWASP LLM Top 10', 'SARIF'];
  scene({
    name: 'standards', from: 'standards', to: 'end',
    build(root, S) {
      S.bg = K.ink(root);
      S.cam = full(root);
      S.eye = K.eyebrow(S.cam, 'Standards alignment', PAD, 200, 'var(--ember)');
      S.t1 = K.head(S.cam, 'EVERY FINDING,', PAD, 262, 130, { color: '#fff' });
      S.t2 = K.head(S.cam, 'TAGGED.', PAD, 400, 130, { color: 'var(--ember)' });
      S.row = el('div', { class: 'abs', style: `left:${PAD}px;top:620px;width:1640px;display:flex;flex-wrap:wrap;gap:16px` }, S.cam);
      S.chips = TAGS.map((s) => reg(el('div', { class: 'mono', style: 'position:relative;padding:16px 24px;border-radius:12px;font-size:32px;font-weight:500;color:#fff;background:rgba(255,255,255,.06);box-shadow:0 0 0 1px rgba(255,255,255,.16);transform-origin:50% 50%' }, S.row, s), { o: 0 }));
      S.sub = K.text(S.cam, 'Mapped to the frameworks your security team already uses.', PAD + 2, 860, { size: 34, color: 'rgba(255,255,255,.72)', w: 1400 });
    },
    run(t, b, S) {
      K.inkRun(t, S.bg, 0.35 + 0.4 * ease.expoIn(seg(t, 166, 171)), 112);
      // build: the camera creeps in, then everything lifts away a beat before the stop
      put(S.cam, K.aim(W / 2, H / 2, 1 + 0.06 * ease.expoIn(seg(t, 164, 171))));
      const gone = sp(t, 170.3, 'default');
      K.eyebrowRun(t, S.eye, 164, 170.2);
      rise(t, S.t1, [164.25, 164.5], 170.3, { exit: 0.3 });
      rise(t, S.t2, [164.75], 170.3, { exit: 0.3 });
      S.chips.forEach((c, i) => {
        const p = spHit(t, 165.5 + i * 0.5, 'snappy');
        const lit = Math.exp(-Math.max(0, t - bt(165.5 + i * 0.5)) * 5) * (p > 0.002 ? 1 : 0);
        put(c, { o: p > 0.002 ? 1 - gone : 0, s: 0.85 + 0.15 * p, y: -160 * gone * (1 + i * 0.15), css: { background: `rgba(194,69,45,${(0.06 + 0.6 * lit).toFixed(3)})` } });
      });
      K.textRun(t, S.sub, 168.5, 170.2);
    },
  });

  // ------------------------------------------------------------------ 17 · end: the lockup and the address (b172 → b180)
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
      put(S.cam, K.aim(W / 2, H / 2, 1.0 + 0.045 * ease.inOut(seg(t, 172, 180))));
      const m = spHit(t, 'end', 'playful');
      put(S.mark, { o: m > 0.002 ? 1 : 0, s: 0.55 + 0.45 * m, r: -10 * (1 - m) });
      rise(t, S.word, [172, 172.25, 172.5]);
      rise(t, S.tag, [173, 173.12, 173.25, 173.5, 173.62, 173.75]);
      K.eyebrowRun(t, S.eye, 'cta');
      rise(t, S.url, [174.25]);
      const u = sp(t, 175, 'default');
      put(S.rule, { o: u > 0.002 ? 1 : 0, sx: u });
    },
  });
})();
