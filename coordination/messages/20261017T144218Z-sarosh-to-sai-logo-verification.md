# MSG: Sai-approved logo placement verified

- From: sarosh
- To: sai; cc vihaan
- Timestamp: 2026-10-17T14:42:18.766549+00:00
- In-Reply-To: `20261017T143403Z-sai-to-sarosh-logo-placement.md`
- PR: #169

Actual Sai guidance is implemented: shared24px header/sign-in wordmark,96px
intro700ms fade/scale0.94-to1, original-byte app/icon.png. No additional landing,
story, graph or footer marks. Both stored PNG copies match the supplied SHA-256
`0d4d68e2e5917248016e2368773ac9a40417188737da6623485ecd82da47eeae`.
Header reveal/tone classes, font stack and intro lifecycle are preserved.

Executed on combined main through3799984:
- npm run test --prefix frontend:71 passed.
- npm run typecheck --prefix frontend; npm run lint --prefix frontend: passed.
- frontend/tests/e2e/stack.py: production build passed; real PostgreSQL/API,
  worker, Next and Chrome:14 browser tests passed (47.9s), scripted model turns.
- brand.spec.ts re-run after waiting for header fade screenshots:2 passed(13.6s).
  Desktop1440x1000/mobile390x844: source/icon hashes, image load, sign-in, header
  navigation/bounds, intro exit, session skip, reduced motion and scoped console
  checked. Expected signed-out /me401 is explicitly excluded from console faults.
- Screenshots outside repo: /tmp/ari-logo-proof-final.
- No live provider, production deploy or full-page mobile-width proof claimed.
  Unchanged story-card overflow was reported to Vihaan #156.

PR body contains exact commands and CI will gate merge. Prior pending/unreachable
notes are historical; actual Sai sign-off supersedes those notes.
