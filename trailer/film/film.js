// THE FILM: scenes are registered act by act (act1.js … act5.js; scene order = paint order).
// Last comes the fx overlay: the scout ant that pulls one scene across the next (its wipe edges live in the scenes).
(() => {
  const { W, H, scene, canvas, seg, ease, bt, lerp } = C;
  const WIPES = [[79, 80, 560], [151, 152, 560]];                                     // [from beat, to beat, ant height]
  scene({
    name: 'fx', from: 0, to: 'done',
    build(root, S) { S.ctx = canvas(root); S.ctx.canvas.style.pointerEvents = 'none'; },
    run(t, b, S) {
      const g = S.ctx; g.clearRect(0, 0, W, H);
      for (const [b0, b1, y] of WIPES) {
        if (b < b0 - 0.05 || b > b1 + 0.05) continue;
        const p = K.wipe(t, b0, b1), x = lerp(-40, W + 120, p);
        const tr = K.path([{ x: -400, y }, { x: W + 400, y }]);
        K.antOn(g, tr, x + 400, 1, { t, scale: 6, color: K.SCOUT, phase: 1.2 });
      }
    },
  });
  C.start();
})();
