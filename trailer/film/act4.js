// CHAPTER 3: DEFENSE LAB. A practice network (rebuilt from the Defense Lab map), a test attacker, an AI defender that
// picks one move per step, how it learned (reward), the real lab page, and the measured results from the committed
// evaluation bundle shown on the site (frontend/app/lab, rl-defense/results). Simulation only; it only recommends.
(() => {
  const { W, H, el, reg, put, scene, canvas, sp, spHit, seg, clamp, lerp, ease, bt, beatOf } = C;
  const { rise } = TYPE;
  const PAD = K.PAD, TAG = '03 · Defense Lab';
  const full = (root) => reg(el('div', { class: 'abs', style: `width:${W}px;height:${H}px` }, root));

  K.menu('menu3', 'menu3', 'c3', 2, false);
  K.chapter('c3title', 'c3', 'c3_sim', '03', 'DEFENSE LAB', 'After launch, attackers keep trying.');

  // ------------------------------------------------------------------ the practice network (b324 → b360)
  const N = { I: ['Internet', 260, 650], G: ['Gateway', 650, 500], S: ['Sign-in', 1060, 500], A: ['API server', 650, 800], P: ['Payments', 1060, 800], D: ['Database', 1470, 650] };
  const E = [['I', 'G'], ['I', 'A'], ['G', 'S'], ['A', 'P'], ['S', 'D'], ['P', 'D']];
  const MOVES = ['Watch closely', 'Slow traffic', 'Cut a machine off', 'Call a human'];
  const RAID1 = [['I', 'G', 332.5], ['G', 'S', 334.5], ['S', 'D', 336.5]];          // no defense: it walks in
  const RAID2 = [['I', 'G', 347.5], ['G', 'S', 350]];                                // defended: stopped at Sign-in
  const at = (path, t) => {                                                          // attacker position on a path
    let p = null;
    for (const [a, z, b0] of path) {
      const k = ease.inOut(seg(t, b0, b0 + 1));
      if (t >= bt(b0)) p = { x: lerp(N[a][1], N[z][1], k), y: lerp(N[a][2], N[z][2], k) };
    }
    return p;
  };
  scene({
    name: 'c3_sim', from: 'c3_sim', to: 'c3_learn',
    build(root, S) {
      S.bg = K.ink(root);
      S.cam = full(root);
      S.ctx = canvas(S.cam);
      S.tag = K.tag(S.cam, TAG);
      S.s1 = K.say(S.cam, ['We built a practice network', 'with a database to protect.'], PAD, 130, { size: 56 });
      S.s2 = K.say(S.cam, ['A test attacker tries to work', 'its way in, one step at a time.'], PAD, 130, { size: 56 });
      S.s3 = K.say(S.cam, ['With no defense,', 'it reaches the database.'], PAD, 130, { size: 56, hl: ['reaches', 'the', 'database.'] });
      S.s4 = K.say(S.cam, ['Now an AI defender watches', 'and makes one move each step.'], PAD, 130, { size: 56, hl: ['AI', 'defender'], hlc: 'var(--ok-dark)' });
      S.nodes = Object.entries(N).map(([k, [name, x, y]]) => {
        const d = reg(el('div', { class: 'abs', style: `left:${x - 130}px;top:${y - 50}px;width:260px;height:100px;border-radius:16px;background:#2b1d19;box-shadow:0 0 0 2px rgba(255,255,255,.12);color:#fff;transform-origin:50% 50%` }, S.cam,
          `<div style="position:absolute;left:22px;top:14px;font:600 32px UI">${name}</div>` + (k === 'D' ? '<div class="eyebrow" style="position:absolute;right:16px;top:20px;font-size:18px;color:var(--ember)">critical</div>' : '') +
          '<div class="mono st" style="position:absolute;left:22px;top:60px;font-size:22px;color:var(--ok-dark)">● Healthy</div>'), { o: 0 });
        d._st = reg(d.querySelector('.st')); d._k = k;
        return d;
      });
      S.moves = reg(el('div', { class: 'abs', style: `left:${PAD}px;top:320px;display:flex;gap:14px` }, S.cam), { o: 0 });
      S.chips = MOVES.map((m) => reg(el('div', { style: 'position:relative;padding:12px 20px;border-radius:12px;background:rgba(79,191,135,.1);box-shadow:0 0 0 2px rgba(79,191,135,.35);font:600 28px UI;color:var(--ok-dark)' }, S.moves, m), { o: 0 }));
      S.badge = reg(el('div', { class: 'abs', style: 'left:1220px;top:880px;padding:14px 22px;border-radius:12px;background:var(--ok-dark);color:#0f2a1c;font:700 32px UI;transform-origin:50% 50%' }, S.cam, '✓ Attack stopped'), { o: 0 });
      S.lost = reg(el('div', { class: 'abs', style: 'left:1300px;top:880px;padding:14px 22px;border-radius:12px;background:#ff6a52;color:#2b0d07;font:700 32px UI;transform-origin:50% 50%' }, S.cam, '✕ Database reached'), { o: 0 });
    },
    run(t, b, S) {
      K.inkRun(t, S.bg, 0.4, 116);
      put(S.cam, K.aim(W / 2, H / 2, 1 + 0.03 * ease.inOut(seg(t, 324, 360))));
      K.eyebrowRun(t, S.tag, 323.8);
      K.sayRun(t, S.s1, 324.5, 330.6); K.sayRun(t, S.s2, 331, 337.6); K.sayRun(t, S.s3, 338, 342.6); K.sayRun(t, S.s4, 343);
      const run2 = b >= 342.5;
      const g = S.ctx; g.clearRect(0, 0, W, H);
      g.lineWidth = 4; g.strokeStyle = 'rgba(255,255,255,.14)';
      for (const [a, z] of E) { const k = sp(t, 325.5, 'default'); g.beginPath(); g.moveTo(N[a][1], N[a][2]); g.lineTo(lerp(N[a][1], N[z][1], k), lerp(N[a][2], N[z][2], k)); g.stroke(); }
      // attacker: a red pulse with a short trail; in run 2 it is cut off at Sign-in
      const p = run2 ? at(RAID2, t) : at(RAID1, t);
      const gone = run2 ? sp(t, 353.5, 'default') : 0;
      if (p && (!run2 || b >= 347.4) && gone < 0.99) {
        const pulse = 0.5 + 0.5 * Math.sin(t * 9);
        g.fillStyle = `rgba(255,106,82,${(0.25 * (1 - gone)).toFixed(3)})`; g.beginPath(); g.arc(p.x, p.y, 34 + 10 * pulse, 0, Math.PI * 2); g.fill();
        g.fillStyle = `rgba(255,106,82,${(1 - gone).toFixed(3)})`; g.beginPath(); g.arc(p.x, p.y, 16 * (1 - 0.6 * gone), 0, Math.PI * 2); g.fill();
      }
      const st = (k) => {                                                // node status this frame
        if (!run2) {
          if (k === 'G' && b >= 333.5) return ['● Attacker got in', '#ff8a78'];
          if (k === 'S' && b >= 335.5) return ['● Attacker got in', '#ff8a78'];
          if (k === 'D' && b >= 337.5) return ['● Reached', '#ff8a78'];
          return null;
        }
        if (k === 'G' && b >= 349) return ['● Watched closely', 'var(--ok-dark)'];
        if (k === 'S' && b >= 353) return ['● Cut off', 'var(--ok-dark)'];
        if (k === 'S' && b >= 351.5) return ['● Traffic slowed', 'var(--ok-dark)'];
        return null;
      };
      S.nodes.forEach((d, i) => {
        const pp = spHit(t, 326 + i * 0.4, 'snappy'), s = st(d._k);
        const red = s && s[1] === '#ff8a78', act = s && !red;
        put(d, { o: pp > 0.002 ? 1 : 0, s: 0.85 + 0.15 * pp, css: { boxShadow: red ? '0 0 0 3px #ff6a52' : act ? '0 0 0 3px var(--ok-dark)' : '0 0 0 2px rgba(255,255,255,.12)', background: red && d._k === 'D' ? '#4a1a12' : '#2b1d19' } });
        put(d._st, { html: s ? s[0] : '● Healthy', css: { color: s ? s[1] : 'var(--ok-dark)' } });
      });
      const mv = sp(t, 344.5, 'default'); put(S.moves, { o: mv > 0.002 ? 1 : 0 });
      const used = [[0, 349], [1, 351.5], [2, 353]];
      S.chips.forEach((c, i) => {
        const p = spHit(t, 345 + i * 0.5, 'snappy'), u = used.find(([k]) => k === i), on = u && t > bt(u[1]) ? Math.exp(-(t - bt(u[1])) * 1.6) : 0;
        put(c, { o: p > 0.002 ? 1 : 0, s: (0.85 + 0.15 * p) * (1 + 0.08 * on), css: { background: `rgba(79,191,135,${(0.1 + 0.55 * on).toFixed(3)})`, color: on > 0.4 ? '#0f2a1c' : 'var(--ok-dark)' } });
      });
      const ok = spHit(t, 355, 'snappy'), bad = spHit(t, 338, 'snappy') * (1 - sp(t, 342.3, 'snappy'));
      put(S.badge, { o: ok > 0.002 ? 1 : 0, s: 0.8 + 0.2 * ok });
      put(S.lost, { o: bad > 0.002 ? 1 : 0, s: 0.8 + 0.2 * bad });
    },
  });

  // ------------------------------------------------------------------ how it learned (b360 → b376)
  scene({
    name: 'c3_learn', from: 'c3_learn', to: 'c3_real',
    build(root, S) {
      S.bg = K.ink(root);
      S.cam = full(root);
      S.ctx = canvas(S.cam);
      S.tag = K.tag(S.cam, TAG);
      S.s1 = K.say(S.cam, ['It learned by practicing,', 'thousands of times.'], PAD, 130, { size: 56 });
      S.s2 = K.say(S.cam, ['Points for stopping attacks.', 'Penalties for getting in users\' way.'], PAD, 130, { size: 56 });
      S.ill = K.eyebrow(S.cam, 'Illustration · the idea, not a measurement', PAD, 930, 'rgba(255,255,255,.5)', 22);
      S.ax = K.eyebrow(S.cam, 'Practice runs →', PAD + 760, 880, 'rgba(255,255,255,.6)', 22);
      S.ay = K.eyebrow(S.cam, 'Attacks stopped', PAD, 330, 'rgba(255,255,255,.6)', 22);
      S.rw = [['+ Stopped an attack', 'var(--ok-dark)', 'rgba(79,191,135,.12)'], ['− Let the attacker in', '#ff8a78', 'rgba(255,106,82,.12)'], ['− Blocked real users', '#ff8a78', 'rgba(255,106,82,.12)']]
        .map(([s, c, bg], i) => reg(el('div', { class: 'abs', style: `left:1260px;top:${420 + i * 110}px;padding:18px 26px;border-radius:14px;background:${bg};color:${c};font:600 36px UI;transform-origin:0 50%` }, S.cam, s), { o: 0 }));
    },
    run(t, b, S) {
      K.inkRun(t, S.bg, 0.35, 116);
      put(S.cam, K.aim(W / 2, H / 2, 1 + 0.03 * ease.inOut(seg(t, 360, 376))));
      K.eyebrowRun(t, S.tag, 359.8);
      K.sayRun(t, S.s1, 360.5, 366.6); K.sayRun(t, S.s2, 367);
      K.eyebrowRun(t, S.ill, 361); K.eyebrowRun(t, S.ax, 361); K.eyebrowRun(t, S.ay, 361);
      const g = S.ctx; g.clearRect(0, 0, W, H);
      const X0 = PAD, Y0 = 860, CWD = 1000, CHT = 470;
      g.strokeStyle = 'rgba(255,255,255,.2)'; g.lineWidth = 2; g.beginPath(); g.moveTo(X0, Y0 - CHT); g.lineTo(X0, Y0); g.lineTo(X0 + CWD, Y0); g.stroke();
      const k = ease.inOut(seg(t, 361, 366.5)), r = C.noise1(9), n = 160;
      g.strokeStyle = 'var(--ember)'; g.strokeStyle = '#e0684a'; g.lineWidth = 5; g.lineJoin = 'round'; g.beginPath();
      for (let i = 0; i <= n * k; i++) { const u = i / n, y = 0.08 + 0.8 * (1 - Math.exp(-4.2 * u)) + 0.05 * r(u * 30) * (1 - u * 0.6); const x = X0 + u * CWD, yy = Y0 - y * CHT; i ? g.lineTo(x, yy) : g.moveTo(x, yy); }
      g.stroke();
      S.rw.forEach((c, i) => { const p = spHit(t, 368 + i * 1, 'snappy'); put(c, { o: p > 0.002 ? 1 : 0, s: 0.85 + 0.15 * p, x: 30 * (1 - p) }); });
    },
  });

  // ------------------------------------------------------------------ the real lab (b376 → b396)
  const SX = 720, SY = 120, SW = 1060, SH = 840, FULLZ = SW / 1920;
  const CAM = [[376, { x: 640, y: 330, z: 0.95 }], [382, { x: 960, y: 520, z: FULLZ * 1.05 }], [389, { x: 950, y: 745, z: 0.82 }]];
  const CAPS = [[['This is Defense Lab,', 'live on the Ari site.'], 376.5, 381.6], [['Pick a defender, press', 'play, and watch every', 'move it made.'], 382, 388.6],
    [['It\'s scored against', 'simpler defenders.'], 389, null]];
  scene({
    name: 'c3_real', from: 'c3_real', to: 'c3_results',
    build(root, S) {
      S.bg = K.ink(root);
      S.cam = full(root);
      S.tag = K.tag(S.cam, TAG);
      S.caps = CAPS.map(([l]) => K.say(S.cam, l, PAD, 400, { size: 46, gap: 1.25 }));
      S.win = K.window(S.cam, [['lab.jpg', 0], ['lab_s1.jpg', 0], ['lab_s2.jpg', 0]], { x: SX, y: SY, w: SW, h: SH, url: 'ari-ai-lake.vercel.app/lab' });
    },
    run(t, b, S) {
      K.inkRun(t, S.bg, 0.6, 110);
      K.eyebrowRun(t, S.tag, 375.8);
      CAPS.forEach(([, a, z], i) => K.sayRun(t, S.caps[i], a, z));
      K.windowRun(S.win, [b < 382 ? 0 : b < 389 ? 1 : 2], K.camAt(t, CAM), sp(t, 376, 'default'));
    },
  });

  // ------------------------------------------------------------------ the results (b396 → b412)
  const STATS = [[7.1, '%', 'of test attacks reached their goal', '100% with no defense'], [94.4, '%', 'of the time, services stayed up', '93.3% with simple rules'],
    [25.6, '', 'steps to stop an attack', '158.3 with simple rules']];
  const DEALS = [399, 400.5, 402];
  scene({
    name: 'c3_results', from: 'c3_results', to: 'c3_honest',
    build(root, S) {
      S.bg = K.ink(root);
      S.cam = full(root);
      S.tag = K.tag(S.cam, TAG);
      S.s1 = K.say(S.cam, ['Tested on 1,500 attacks', 'it never practiced on:'], PAD, 130, { size: 56 });
      S.cards = STATS.map(([, , lab, vs], i) => {
        const c = reg(el('div', { class: 'abs', style: `left:${PAD + i * 556}px;top:400px;width:528px;height:440px;border-radius:22px;background:rgba(255,255,255,.05);box-shadow:0 0 0 1px rgba(255,255,255,.1);color:#fff;transform-origin:50% 100%` }, S.cam,
          `<div class="mono" style="position:absolute;left:34px;top:46px;font-size:132px;font-weight:600;letter-spacing:-.04em;line-height:1;color:var(--ok-dark)"></div>` +
          `<div style="position:absolute;left:36px;top:214px;width:450px;font:600 36px UI;line-height:1.25">${lab}</div>` +
          `<div class="eyebrow" style="position:absolute;left:36px;top:360px;font-size:24px;color:rgba(255,255,255,.55)">vs ${vs}</div>`), { o: 0 });
        c._n = reg(c.firstChild);
        return c;
      });
    },
    run(t, b, S) {
      K.inkRun(t, S.bg, 0.45, 114);
      put(S.cam, K.aim(W / 2, H / 2, 1 + 0.03 * ease.inOut(seg(t, 396, 412))));
      K.eyebrowRun(t, S.tag, 395.8);
      K.sayRun(t, S.s1, 396.5);
      S.cards.forEach((c, i) => {
        const p = spHit(t, DEALS[i], 'snappy'), [v, suf] = STATS[i];
        put(c, { o: p > 0.002 ? 1 : 0, y: 120 * (1 - p), s: 0.92 + 0.08 * p });
        put(c._n, { text: `${(v * ease.out(seg(t, DEALS[i], DEALS[i] + 1.5))).toFixed(1)}${suf}` });
      });
    },
  });

  // ------------------------------------------------------------------ it recommends, you decide (b412 → b420)
  scene({
    name: 'c3_honest', from: 'c3_honest', to: 'loop',
    build(root, S) {
      S.bg = K.ink(root);
      S.cam = full(root);
      S.tag = K.tag(S.cam, TAG);
      S.l1 = K.head(S.cam, 'IT RECOMMENDS.', PAD, 300, 170, { color: '#fff' });
      S.l2 = K.head(S.cam, 'YOU DECIDE.', PAD, 470, 170, { color: 'var(--ember)' });
      S.sub = K.say(S.cam, ['It trains in a simulation and never', 'touches your real systems on its own.'], PAD, 720, { size: 50 });
    },
    run(t, b, S) {
      K.inkRun(t, S.bg, 0.6, 112);
      put(S.cam, K.aim(W / 2, H / 2, 1 + 0.05 * ease.inOut(seg(t, 412, 420))));
      K.eyebrowRun(t, S.tag, 411.8, 419.3);
      rise(t, S.l1, [412.5, 413], 419.5, { exit: 0.3 });
      rise(t, S.l2, [413.5, 414], 419.5, { exit: 0.3 });
      K.sayRun(t, S.sub, 415, 419.4);
    },
  });
})();
