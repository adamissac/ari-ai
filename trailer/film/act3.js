// CHAPTER 2: THE SECURITY TEAM. Seven narrow agents (docs/07): who they are, why each only gets the tools its job
// needs (the capability matrix), how they hand proof along like a relay with a human approval gate, a real run.
(() => {
  const { W, H, el, reg, put, scene, canvas, sp, spHit, seg, clamp, lerp, ease, bt, beatOf } = C;
  const { rise } = TYPE;
  const PAD = K.PAD, TAG = '02 · The Security Team';
  const full = (root) => reg(el('div', { class: 'abs', style: `width:${W}px;height:${H}px` }, root));

  K.menu('menu2', 'menu2', 'c2', 1, false);
  K.chapter('c2title', 'c2', 'c2_team', '02', 'THE SECURITY TEAM', 'Even code that works can be hacked.');

  // ------------------------------------------------------------------ seven agents, one job each (b196 → b216)
  const AG = [['Scout', 'Looks for weak spots', 'Red'], ['Probe', 'Safely tests if they are real', 'Red'], ['Trace', 'Follows how far an attacker could get', 'Red'],
    ['Diagnose', 'Finds the root cause', 'Blue'], ['Patch', 'Writes the fix', 'Blue'], ['Fortify', 'Stops it happening again', 'Blue'], ['Verify', 'Double-checks, on its own', 'Judge']];
  const DEAL = [199, 199.5, 200, 201.5, 202, 202.5, 204];
  const TEAM = { Red: ['Red team', 'var(--ember)', 'rgba(224,104,74,.5)', 206.5], Blue: ['Blue team', '#9cc1ea', 'rgba(156,193,234,.45)', 208], Judge: ['Independent', 'var(--ok-dark)', 'rgba(79,191,135,.5)', 209.5] };
  scene({
    name: 'c2_team', from: 'c2_team', to: 'c2_tools',
    build(root, S) {
      S.bg = K.ink(root);
      S.cam = full(root);
      S.tag = K.tag(S.cam, TAG);
      S.s1 = K.say(S.cam, ['So Ari brings a team of seven', 'AI security agents, one job each.'], PAD, 130, { size: 56 });
      S.s2 = K.say(S.cam, ['Red team thinks like an attacker.', 'Blue team fixes. Verify judges alone.'], PAD, 130, { size: 56 });
      S.cards = AG.map(([name, role, team], i) => {
        const [lab, col, edge] = TEAM[team];
        const c = reg(el('div', { class: 'abs', style: `left:${PAD + i * 236}px;top:400px;width:220px;height:420px;border-radius:20px;background:#2b1d19;box-shadow:0 0 0 1px rgba(255,255,255,.12);color:#fff;transform-origin:50% 100%` }, S.cam,
          `<div class="eyebrow" style="position:absolute;left:20px;top:20px;font-size:19px;color:${col}">${lab}</div>` +
          `<div class="mark" style="position:absolute;left:20px;top:80px;width:84px;height:60px;color:${col}"></div>` +
          `<div class="display" style="position:absolute;left:20px;top:176px;font-size:42px;text-transform:none;letter-spacing:-.03em">${name}</div>` +
          `<div style="position:absolute;left:20px;top:240px;width:182px;font:500 27px UI;line-height:1.25;color:rgba(255,255,255,.8)">${role}</div>`), { o: 0 });
        c._edge = edge; c._team = team;
        return c;
      });
    },
    run(t, b, S) {
      K.inkRun(t, S.bg, 0.55, 116);
      put(S.cam, K.aim(W / 2, H / 2, 1 + 0.035 * ease.inOut(seg(t, 196, 216))));
      K.eyebrowRun(t, S.tag, 195.8);
      K.sayRun(t, S.s1, 196.5, 205.6);
      K.sayRun(t, S.s2, 206);
      S.cards.forEach((c, i) => {
        const at = TEAM[c._team][3], p = spHit(t, DEAL[i], 'snappy'), lit = spHit(t, at, 'snappy');
        const glow = t > bt(at) ? Math.exp(-(t - bt(at)) * 2.5) : 0;
        put(c, { o: p > 0.002 ? 1 : 0, y: 140 * (1 - p) - 18 * glow, r: 5 * (1 - p), s: 0.9 + 0.1 * p,
          css: { boxShadow: lit > 0.5 ? `0 0 0 3px ${c._edge}, 0 40px 90px -30px rgba(0,0,0,.6)` : '0 0 0 1px rgba(255,255,255,.12)' } });
      });
    },
  });

  // ------------------------------------------------------------------ only the tools each job needs (b216 → b232)
  const COLS = ['Read code', 'Run code', 'Change code', 'Use network'];
  // docs/07 capability matrix in plain words: '' = not allowed, 'yes' = allowed, anything else = allowed only that way
  const CAN = { Scout: ['yes', '', '', ''], Probe: ['yes', 'sandbox only', '', 'test target only'], Trace: ['yes', '', '', ''], Diagnose: ['yes', '', '', ''],
    Patch: ['yes', 'scratch copy', 'scratch copy', ''], Fortify: ['yes', '', 'suggests only', ''], Verify: ['the fix only', 'fresh sandbox', '', 'test target only'] };
  const GX0 = PAD, GY0 = 360, NAMEW = 300, COLW = 335, ROWH = 74;
  scene({
    name: 'c2_tools', from: 'c2_tools', to: 'c2_relay',
    build(root, S) {
      S.bg = K.ink(root);
      S.cam = full(root);
      S.tag = K.tag(S.cam, TAG);
      S.s1 = K.say(S.cam, ['Each agent only gets the tools', 'its one job needs.'], PAD, 130, { size: 56 });
      S.s2 = K.say(S.cam, ['So if one agent is ever tricked,', 'it can\'t do much harm.'], PAD, 130, { size: 56, hl: ['can\'t'] });
      S.head = reg(el('div', { class: 'abs', style: `left:${GX0}px;top:${GY0}px;width:1640px;height:56px;display:flex` }, S.cam,
        `<span style="width:${NAMEW}px"></span>` + COLS.map((c) => `<span class="eyebrow" style="width:${COLW}px;font-size:24px;color:rgba(255,255,255,.6);line-height:56px">${c}</span>`).join('')), { o: 0 });
      S.rows = Object.entries(CAN).map(([name, v], i) => reg(el('div', { class: 'abs', style: `left:${GX0}px;top:${GY0 + 64 + i * ROWH}px;width:1640px;height:${ROWH - 10}px;display:flex;align-items:center;border-radius:12px;background:${i % 2 ? 'rgba(255,255,255,.03)' : 'rgba(255,255,255,.06)'}` }, S.cam,
        `<span style="width:${NAMEW}px;padding-left:22px;box-sizing:border-box;font:600 32px UI;color:#fff">${name}</span>` +
        v.map((x) => x === 'yes' ? `<span style="width:${COLW}px;font:600 30px UI;color:var(--ok-dark)">✓</span>`
          : x ? `<span style="width:${COLW}px;font:500 26px UI;color:var(--ember)">✓ ${x}</span>` : `<span style="width:${COLW}px;font:600 30px UI;color:rgba(255,255,255,.25)">✕</span>`).join('')), { o: 0 }));
    },
    run(t, b, S) {
      K.inkRun(t, S.bg, 0.35, 118);
      put(S.cam, K.aim(W / 2, H / 2, 1 + 0.03 * ease.inOut(seg(t, 216, 232))));
      K.eyebrowRun(t, S.tag, 215.8);
      K.sayRun(t, S.s1, 216.5, 224.1);
      K.sayRun(t, S.s2, 224.5);
      const hd = sp(t, 217.5, 'default'); put(S.head, { o: hd > 0.002 ? 1 : 0, y: -20 * (1 - hd) });
      S.rows.forEach((r, i) => { const p = spHit(t, 218 + i * 0.5, 'snappy'); put(r, { o: p > 0.002 ? 1 : 0, x: -40 * (1 - p) }); });
    },
  });

  // ------------------------------------------------------------------ the relay, with a human approval gate (b232 → b260)
  const CHAIN = [['Scout', 'a suspicion'], ['Probe', 'proof it\'s real'], ['Trace', 'how far it goes'], ['Diagnose', 'the cause + a plan'], ['You', 'your OK'], ['Patch', 'a fix'], ['Verify', 'pass or fail'], ['Fortify', '']];
  const NX = (i) => 230 + i * 208, NY = 600, NR = 62;
  const PASS = [236, 237.5, 239, 240.5, 243, 244.5, 246];         // the baton leaves node i at PASS[i] and lands one beat later
  scene({
    name: 'c2_relay', from: 'c2_relay', to: 'c2_real',
    build(root, S) {
      S.bg = K.ink(root);
      S.cam = full(root);
      S.ctx = canvas(S.cam);
      S.tag = K.tag(S.cam, TAG);
      S.s1 = K.say(S.cam, ['They work like a relay race:', 'each one passes proof to the next.'], PAD, 130, { size: 56 });
      S.s2 = K.say(S.cam, ['A person on your team approves', 'before any fix is written.'], PAD, 130, { size: 56, hl: ['person'] });
      S.s3 = K.say(S.cam, ['If Verify rejects a fix,', 'Patch has to try again.'], PAD, 130, { size: 56 });
      S.s4 = K.say(S.cam, ['All testing happens in a sealed copy', 'of your app, never the real one.'], PAD, 130, { size: 56, hl: ['sealed', 'copy'] });
      S.nodes = CHAIN.map(([n], i) => {
        const you = n === 'You';
        const d = reg(el('div', { class: 'abs', style: `left:${NX(i) - NR}px;top:${NY - NR}px;width:${NR * 2}px;height:${NR * 2}px;border-radius:${you ? '22px' : '50%'};background:${you ? 'var(--accent)' : '#2b1d19'};box-shadow:0 0 0 2px rgba(255,255,255,.14);display:grid;place-items:center;transform-origin:50% 50%` }, S.cam,
          you ? '<span style="font:700 26px UI;color:#fff">YOU</span>' : `<span class="mark" style="width:62px;height:44px;color:${i < 3 ? 'var(--ember)' : i === 6 ? 'var(--ok-dark)' : '#cfe0f3'}"></span>`), { o: 0 });
        d._label = reg(el('div', { class: 'abs', style: `left:${NX(i) - 110}px;top:${NY + NR + 18}px;width:220px;text-align:center;font:600 30px UI;color:#fff` }, S.cam, you ? 'You approve' : n), { o: 0 });
        return d;
      });
      S.pins = CHAIN.slice(0, -1).map(() => reg(el('div', { class: 'abs' }, S.cam)));
      S.batons = CHAIN.slice(0, -1).map(([, what], i) => reg(el('div', { style: 'position:absolute;left:0;top:0;padding:8px 14px;border-radius:10px;background:#fff;color:var(--ink);font:600 24px UI;white-space:nowrap;transform:translate(-50%,-50%)' }, S.pins[i], what), { o: 0 }));
      S.rej = reg(el('div', { class: 'abs eyebrow', style: `left:${NX(5) + 20}px;top:${NY + 210}px;color:#ff8a78;font-size:24px` }, S.cam, '✕ rejected: try again'), { o: 0 });
      S.box = reg(el('div', { class: 'abs', style: `left:${NX(1) - 120}px;top:${NY - 150}px;width:${NX(6) - NX(1) + 240}px;height:420px;border:3px dashed rgba(224,104,74,.8);border-radius:34px` }, S.cam), { o: 0 });
      S.boxL = reg(el('div', { class: 'abs eyebrow', style: `left:${NX(1) - 96}px;top:${NY - 196}px;color:var(--ember);font-size:24px` }, S.cam, 'Sealed test copy'), { o: 0 });
    },
    run(t, b, S) {
      K.inkRun(t, S.bg, 0.4, 116);
      put(S.cam, K.aim(W / 2, H / 2, 1 + 0.03 * ease.inOut(seg(t, 232, 260))));
      K.eyebrowRun(t, S.tag, 231.8);
      K.sayRun(t, S.s1, 232.5, 246.6); K.sayRun(t, S.s2, 247, 251.6); K.sayRun(t, S.s3, 252, 255.6); K.sayRun(t, S.s4, 256);
      const g = S.ctx; g.clearRect(0, 0, W, H);
      for (let i = 0; i < CHAIN.length - 1; i++) {
        const k = ease.inOut(seg(t, PASS[i], PASS[i] + 1)), on = sp(t, 233.5 + i * 0.25, 'default');
        g.strokeStyle = 'rgba(255,255,255,.14)'; g.lineWidth = 3; g.beginPath(); g.moveTo(NX(i) + NR, NY); g.lineTo(lerp(NX(i) + NR, NX(i + 1) - NR, on), NY); g.stroke();
        if (k > 0) { g.strokeStyle = 'rgba(224,104,74,.9)'; g.beginPath(); g.moveTo(NX(i) + NR, NY); g.lineTo(lerp(NX(i) + NR, NX(i + 1) - NR, k), NY); g.stroke(); }
      }
      const rj = ease.inOut(seg(t, 252.5, 253.75));
      if (rj > 0) {
        g.save(); g.strokeStyle = '#ff8a78'; g.lineWidth = 3; g.setLineDash([10, 10]); g.beginPath();
        const x0 = NX(6), x1 = NX(5), steps = 40;
        for (let s = 0; s <= steps * rj; s++) { const u = s / steps; const x = lerp(x0, x1, u), y = NY + NR + 70 + Math.sin(Math.PI * u) * 90; s ? g.lineTo(x, y) : g.moveTo(x, y); }
        g.stroke(); g.restore();
      }
      put(S.rej, { o: clamp((b - 253.25) * 2) });
      S.nodes.forEach((n, i) => {
        const p = spHit(t, 233 + i * 0.25, 'snappy');
        const hit = i === 0 ? 235.5 : PASS[i - 1] + 1, lit = t > bt(hit) ? Math.exp(-(t - bt(hit)) * 3) : 0;
        const gate = i === 4 ? spHit(t, 247.5, 'snappy') : 0;
        put(n, { o: p > 0.002 ? 1 : 0, s: (0.8 + 0.2 * p) * (1 + 0.12 * lit + 0.1 * gate), css: { boxShadow: `0 0 0 ${(2 + 4 * Math.max(lit, gate)).toFixed(2)}px ${lit > 0.05 || gate > 0.05 ? 'var(--ember)' : 'rgba(255,255,255,.14)'}` } });
        put(n._label, { o: p > 0.002 ? 1 : 0 });
      });
      S.pins.forEach((pin, i) => {
        const k = ease.inOut(seg(t, PASS[i], PASS[i] + 1)), here = b >= PASS[i] - 0.2 && b < PASS[i] + 1.15;
        put(pin, { x: lerp(NX(i), NX(i + 1), k), y: NY - NR - 46 - 30 * Math.sin(Math.PI * k) });
        put(S.batons[i], { o: here ? 1 : 0 });
      });
      const bx = ease.inOut(seg(t, 256.5, 257.75));
      put(S.box, { o: bx > 0.002 ? 1 : 0, clip: C.inset(0, 100 * (1 - bx), 0, 0) });
      put(S.boxL, { o: clamp((b - 257) * 2) });
    },
  });

  // ------------------------------------------------------------------ a real run (b260 → b296)
  const SX = 720, SY = 120, SW = 1060, SH = 840, FULLZ = SW / 1920;
  const SHOTS = ['run_026.jpg', 'run_046.jpg', 'run_076.jpg', 'run_086.jpg', 'run_096.jpg', 'run_116.jpg', 'tab_seven.jpg'];
  const IMG = (b) => (b < 266 ? 0 : b < 267.5 ? 1 : b < 269 ? 2 : b < 270.5 ? 3 : b < 272 ? 4 : b < 287 ? 5 : 6);
  const CAM = [[260, { x: 960, y: 540, z: FULLZ }], [266, { x: 880, y: 500, z: 1.0 }], [274, { x: 700, y: 590, z: 1.32 }],
    [280, { x: 1345, y: 595, z: 1.5 }], [287, { x: 960, y: 640, z: FULLZ * 1.05 }]];
  const CAPS = [[['Here\'s a real run', 'on one code change.'], 260.5, 265.6], [['The agents take turns,', 'one after another.'], 266, 273.6],
    [['Issue found.', 'Fix verified.'], 274, 279.6], [['A pull request waits', 'for your team. Nothing', 'merges on its own.'], 280, 286.6], [['Every step is recorded,', 'so you can replay it.'], 287, null]];
  scene({
    name: 'c2_real', from: 'c2_real', to: 'c2_why',
    build(root, S) {
      S.bg = K.ink(root);
      S.cam = full(root);
      S.tag = K.tag(S.cam, TAG);
      S.caps = CAPS.map(([l]) => K.say(S.cam, l, PAD, 400, { size: 46, gap: 1.25, hl: ['Issue', 'found.'] }));
      S.win = K.window(S.cam, SHOTS.map((s) => [s, 0]), { x: SX, y: SY, w: SW, h: SH, url: 'ari-ai-lake.vercel.app/demo/lumen-pay/payments-api' });
    },
    run(t, b, S) {
      K.inkRun(t, S.bg, 0.6, 110);
      K.eyebrowRun(t, S.tag, 259.8);
      CAPS.forEach(([, a, z], i) => K.sayRun(t, S.caps[i], a, z));
      K.windowRun(S.win, [IMG(b)], K.camAt(t, CAM), sp(t, 260, 'default'));
    },
  });

  // ------------------------------------------------------------------ why it's different (b296 → b308)
  scene({
    name: 'c2_why', from: 'c2_why', to: 'menu3',
    build(root, S) {
      S.bg = K.ink(root);
      S.cam = full(root);
      S.tag = K.tag(S.cam, TAG);
      S.l1 = K.head(S.cam, 'WHOEVER WRITES THE FIX', PAD, 300, 128, { color: '#fff' });
      S.l2 = K.head(S.cam, 'NEVER GRADES IT.', PAD, 440, 128, { color: 'var(--ember)' });
      S.sub = K.say(S.cam, ['Verify works alone and decides only', 'on real test results.'], PAD, 700, { size: 52 });
    },
    run(t, b, S) {
      K.inkRun(t, S.bg, 0.6, 112);
      put(S.cam, K.aim(W / 2, H / 2, 1 + 0.05 * ease.inOut(seg(t, 296, 308))));
      K.eyebrowRun(t, S.tag, 295.8, 307.2);
      rise(t, S.l1, [296.5, 296.75, 297, 297.25], 307.4, { exit: 0.3 });
      rise(t, S.l2, [298, 298.25, 298.5], 307.4, { exit: 0.3 });
      K.sayRun(t, S.sub, 300.5, 307.3);
    },
  });
})();
