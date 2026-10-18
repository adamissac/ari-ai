// ACT 2: meet Ari. The colony pours out on the drop (the site's hero ants, as a pure function of time),
// the lockup lands, then the brand line. One colony spans both scenes so the cut at the headline is a match cut.
(() => {
  const { W, H, el, reg, put, scene, canvas, sp, spHit, seg, clamp, lerp, ease, bt } = C;
  const { rise } = TYPE;
  const PAD = K.PAD;
  const TRS = K.TRAILS.map((c) => K.trail(c, W, H));
  const COL = K.colony({ trails: TRS, nests: K.NESTS, n: 36, first: 10, seed: 146, speed: 1 });
  const T0 = () => bt('ari') - 0.25;

  // ------------------------------------------------------------------ 4 · ari: the colony and the lockup (b32 → b40)
  scene({
    name: 'ari', from: 'ari', to: 'headline',
    build(root, S) {
      S.bg = K.ink(root);
      S.ctx = canvas(root);
      S.cam = reg(el('div', { class: 'abs', style: `width:${W}px;height:${H}px` }, root));
      S.mark = K.mark(S.cam, 176, '#fff');
      Object.assign(S.mark.style, { left: PAD + 'px', top: '338px', transformOrigin: '50% 100%' });
      S.word = K.head(S.cam, 'A R I', PAD + 280, 322, 250, { color: '#fff' });
      // the wordmark face: Chakra Petch 700 with 0.08em tracking (frontend .ari-wordmark-text); no word spaces
      Object.assign(S.word.el.style, { fontFamily: 'Wordmark', letterSpacing: '0.08em', lineHeight: '1' });
      [...S.word.el.childNodes].filter((n) => n.nodeType === 3).forEach((n) => n.remove());
      S.sub = K.head(S.cam, 'ARI CHECKS EVERY CHANGE.', PAD, 640, 84, { color: '#fff' });
      S.sub.words.slice(2).forEach((w) => (w.style.color = 'var(--ember)'));
      S.eye = K.eyebrow(S.cam, 'An AI engineering and security team', PAD + 4, 780, 'rgba(255,255,255,.6)', 28);
    },
    run(t, b, S) {
      K.inkRun(t, S.bg, 0.55 + 0.45 * sp(t, 'ari', 'heavy'), 108);
      const g = S.ctx; g.clearRect(0, 0, W, H);
      K.colonyDraw(g, COL, t - T0(), { scale: 1.7 });
      put(S.cam, K.aim(W / 2, H / 2, 1.0 + 0.05 * ease.inOut(seg(t, 32, 40))));
      const m = spHit(t, 'ari', 'playful');                 // the ant is the mascot: the one playful spring in the film
      put(S.mark, { o: m > 0.002 ? 1 : 0, s: 0.55 + 0.45 * m, r: -10 * (1 - m) });
      rise(t, S.word, [32, 32.25, 32.5]);
      rise(t, S.sub, [34, 34.25, 34.5, 34.75]);
      K.eyebrowRun(t, S.eye, 36);
    },
  });

  // ------------------------------------------------------------------ 5 · headline: find the flaw, prove the fix (b40 → b48)
  scene({
    name: 'headline', from: 'headline', to: 'loop',
    build(root, S) {
      S.bg = K.ink(root);
      S.ctx = canvas(root);
      S.cam = reg(el('div', { class: 'abs', style: `width:${W}px;height:${H}px` }, root));
      S.l1 = K.head(S.cam, 'FIND THE FLAW.', PAD, 236, 180, { color: '#fff' });
      S.l2 = K.head(S.cam, 'PROVE THE FIX.', PAD, 416, 180, { color: 'var(--ember)' });
      S.tag = K.text(S.cam, 'A repair counts only when independent, executed tests agree.', PAD + 4, 676, { size: 40, color: 'rgba(255,255,255,.8)', w: 1300 });
    },
    run(t, b, S) {
      K.inkRun(t, S.bg, 1, 108);
      const g = S.ctx; g.clearRect(0, 0, W, H);
      K.colonyDraw(g, COL, t - T0(), { scale: 1.7 });
      put(S.cam, K.aim(W / 2, H / 2, 1 + 0.05 * ease.inOut(seg(t, 40, 48))));
      rise(t, S.l1, [40, 40.5, 41], 47.7, { exit: 0.3 });
      rise(t, S.l2, [42, 42.5, 43], 47.7, { exit: 0.3 });
      K.textRun(t, S.tag, 44, 47.6);
    },
  });
})();
