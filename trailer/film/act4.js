// ACT 4: the real product. Captured screens of the demo console (frontend/app/demo/..., recorded run on
// lumen-pay/payments-api @ 06e0663) and Defense Lab, driven by a beat-locked camera. Nothing here is redrawn UI
// except the cursor and the click ripple.
(() => {
  const { W, H, el, reg, put, scene, sp, spHit, trkObj, seg, clamp, lerp, ease, bt } = C;
  const { rise } = TYPE;
  const PAD = K.PAD;
  const full = (root) => reg(el('div', { class: 'abs', style: `width:${W}px;height:${H}px` }, root));
  const L = Math.log;
  /** Camera on a page: keys [[beat, {x, y, z}, preset?]]; zoom springs in log space so pushes feel even. */
  const camAt = (t, keys) => { const k = trkObj(t, keys.map(([b, v, p]) => [b, { x: v.x, y: v.y, lz: L(v.z) }, p]), 'heavy'); return { x: k.x, y: k.y, z: Math.exp(k.lz) }; };
  const CURSOR = '<svg width="34" height="46" viewBox="0 0 22 30"><path d="M1 1 L1 25 L7.2 19.2 L11.4 28.6 L15.4 26.8 L11.3 17.6 L19.5 17.6 Z" fill="#fff" stroke="#1c1210" stroke-width="1.4" stroke-linejoin="round"/></svg>';

  // ------------------------------------------------------------------ 13 · console: watch it run, what Ari found, the review (b112 → b144)
  const SHOTS = ['run_016.jpg', 'run_026.jpg', 'run_046.jpg', 'run_076.jpg', 'run_086.jpg', 'run_096.jpg', 'run_116.jpg', 'tab_code.jpg', 'tab_code_s1.jpg'];
  const SX = 210, SY = 128, SW = 1500, SH = 844, BAR = 46, CY = BAR + (SH - BAR) / 2;
  const CAM = [
    [112, { x: 418, y: 600, z: 1.9 }],
    [115.5, { x: 418, y: 618, z: 2.6 }],                   // lean in on "Watch the agents"
    [120, { x: 960, y: 540, z: SW / 1920 }],               // the drop: pull back to the whole run
    [120.75, { x: 895, y: 512, z: 1.18 }],                 // the agents step through
    [125, { x: 700, y: 590, z: 1.5 }],                     // what Ari found
    [127, { x: 690, y: 655, z: 2.05 }],
    [129, { x: 1345, y: 595, z: 1.75 }],                   // what happens next
    [131, { x: 960, y: 480, z: 0.95 }],
    [132, { x: 1500, y: 182, z: 2.4 }],                    // issue found · fix verified
    [133.25, { x: 560, y: 330, z: 1.7 }],                  // tabs: the cursor goes to Code review
    [135, { x: 680, y: 475, z: 1.45 }],                    // the intent
    [136.5, { x: 960, y: 705, z: 1.2 }],                   // should always do / reviewer flagged
    [138.5, { x: 720, y: 1095, z: 1.25 }],                 // the code that changed (tall page: second capture at +760)
    [140, { x: 720, y: 1392, z: 1.6 }],                    // the fix, verified
    [141.5, { x: 960, y: 1655, z: 1.4 }],                  // the tests Ari wrote
  ];
  const IMG = (b) => (b < 120 ? 0 : b < 121 ? 1 : b < 122 ? 2 : b < 123 ? 3 : b < 124 ? 4 : b < 125 ? 5 : b < 135 ? 6 : 7);
  const CAPS = [['Replay of a recorded run · payments-api @ 06e0663', 114.9, 124.6], ['One finding · repaired · verified · nothing merged', 125.2, 132.9], ['The review · the tests Ari wrote', 135.2, null]];
  scene({
    name: 'console', from: 'build2', to: 'lab',
    build(root, S) {
      S.bg = K.ink(root);
      S.cam = full(root);
      S.w1 = K.head(S.cam, 'WATCH IT RUN.', PAD, 420, 190, { color: '#fff' });
      S.w1.words[2].style.color = 'var(--ember)';
      S.caps = CAPS.map(([s]) => K.eyebrow(S.cam, s, SX + 4, 62, 'rgba(255,255,255,.62)', 24));
      S.scr = K.screen(S.cam, SHOTS, { x: SX, y: SY, w: SW, h: SH, radius: 18 });
      S.scr.box.style.transformOrigin = '50% 100%';
      S.scr.box.style.boxShadow = '0 0 0 1px rgba(255,255,255,.16), 0 60px 140px -30px rgba(0,0,0,.7)';
      // browser chrome around the captured page, so it reads as the live site (rebuilt; monochrome on purpose)
      const dot = '<i style="display:block;width:13px;height:13px;border-radius:50%;background:rgba(255,255,255,.22)"></i>';
      el('div', { class: 'abs', style: `left:0;top:0;width:${SW}px;height:${BAR}px;background:#241815;border-bottom:1px solid rgba(255,255,255,.08);display:flex;align-items:center;gap:9px;padding:0 20px;box-sizing:border-box` }, S.scr.box,
        `${dot}${dot}${dot}<span class="mono" style="margin-left:22px;padding:6px 18px;border-radius:8px;background:rgba(255,255,255,.06);font-size:19px;color:rgba(255,255,255,.62)">ari-ai-lake.vercel.app/demo/lumen-pay/payments-api</span>`);
      S.scr.imgs[8].style.top = '760px';
      // the one failing-then-passing test, outlined on the page (page px of tab_code_s1 + 760)
      S.hl = reg(el('div', { class: 'abs', style: 'left:326px;top:1640px;width:1282px;height:42px;border:3px solid var(--ember);border-radius:10px' }, S.scr.cam), { o: 0 });
      S.ripple = reg(el('div', { class: 'abs', style: 'width:80px;height:80px;margin:-40px 0 0 -40px;border-radius:50%;border:3px solid #fff;transform-origin:40px 40px' }, S.scr.box), { o: 0 });
      S.cursor = reg(el('div', { class: 'abs', style: 'width:34px;height:46px;filter:drop-shadow(0 6px 10px rgba(0,0,0,.45))' }, S.scr.box, CURSOR), { o: 0 });
    },
    run(t, b, S) {
      K.inkRun(t, S.bg, 0.45 + 0.5 * sp(t, 'product', 'heavy'), 110);
      rise(t, S.w1, [112.5, 113, 113.5], 114.5, { exit: 0.3 });
      CAPS.forEach(([, a, z], i) => K.eyebrowRun(t, S.caps[i], a, z));
      // the window rises as a card and settles from a slight tilt; it stays put while the camera works inside it
      const up = sp(t, 114.75, 'default');
      put(S.scr.box, { o: up > 0.002 ? 1 : 0, y: 760 * (1 - up), r: -4 * (1 - up), s: 0.9 + 0.1 * up });
      const c = camAt(t, CAM), i = IMG(b);
      S.scr.imgs.forEach((im, k) => put(im, { o: k === i || (i === 7 && k === 8) ? 1 : 0 }));
      put(S.scr.cam, { x: SW / 2 - c.x * c.z, y: CY - c.y * c.z, s: c.z });
      const hl = spHit(t, 142.5, 'snappy');
      put(S.hl, { o: hl > 0.002 ? 1 : 0, s: 1 + 0.04 * (1 - hl), css: { transformOrigin: '50% 50%' } });
      // the cursor: page point → window point through the camera
      const win = (px, py) => ({ x: SW / 2 + (px - c.x) * c.z, y: CY + (py - c.y) * c.z });
      const moves = [[115.75, 117.25, 117.5, { x: 1260, y: 760 }, [418, 622]], [133.6, 134.25, 134.5, { x: 1300, y: 640 }, [405, 348]]];
      let cur = null;
      for (const [m0, m1, click, from, [px, py]] of moves) {
        if (b < m0 - 0.2 || b > click + 0.75) continue;
        const k = ease.inOut(seg(t, m0, m1)), to = win(px, py);
        const press = Math.exp(-Math.max(0, t - bt(click)) * 12) * (t > bt(click) ? 1 : 0);
        cur = { x: lerp(from.x, to.x, k), y: lerp(from.y, to.y, k), s: 1 - 0.18 * press, o: clamp((b - (m0 - 0.2)) / 0.2) * (1 - clamp((b - click - 0.5) / 0.25)) };
        const rp = seg(t, click, click + 0.75);
        put(S.ripple, { o: rp > 0 && rp < 1 ? 1 - rp : 0, x: to.x, y: to.y, s: 0.3 + 1.4 * ease.out(rp) });
      }
      put(S.cursor, cur ? { o: cur.o, x: cur.x, y: cur.y, s: cur.s } : { o: 0 });
      put(S.cam, K.aim(W / 2, H / 2, 1 + 0.02 * Math.sin((t - bt(112)) * 0.4)));
    },
  });

  // ------------------------------------------------------------------ 14 · lab: can an AI learn to defend a network? (b144 → b152)
  const LAB = [
    [144, { x: 640, y: 300, z: 1.5 }],
    [145, { x: 690, y: 320, z: 1.35 }],
    [146, { x: 960, y: 520, z: 1.0 }],                     // the isolated test network
    [147.5, { x: 1010, y: 570, z: 1.55 }],                 // the defender watching Payments
    [149, { x: 960, y: 745, z: 1.3 }],                     // who defends best
    [150.5, { x: 560, y: 760, z: 1.9 }],                   // 7.1% of attacks reached their goal
  ];
  scene({
    name: 'lab', from: 'lab', to: 'proof',
    build(root, S) {
      root.style.background = '#1c1210';
      S.scr = K.screen(root, ['lab.png', 'lab_s1.png', 'lab_s2.png'], { x: 0, y: 0, w: W, h: H, radius: 0 });
      S.scr.box.style.boxShadow = 'none';
      S.tag = K.eyebrow(root, 'Defense Lab · isolated test network · simulation only', PAD, 990, '#fff', 24);
      S.tag.style.cssText += ';background:rgba(28,18,16,.82);padding:10px 16px;border-radius:8px';
    },
    run(t, b, S) {
      put(S.scr.box, { o: 1 });
      const c = camAt(t, LAB), i = b < 146 ? 0 : b < 149 ? 1 : 2;
      S.scr.imgs.forEach((im, k) => put(im, { o: k === i ? 1 : 0 }));
      put(S.scr.cam, { x: W / 2 - c.x * c.z, y: H / 2 - c.y * c.z, s: c.z });
      K.eyebrowRun(t, S.tag, 144.5);
    },
  });
})();
