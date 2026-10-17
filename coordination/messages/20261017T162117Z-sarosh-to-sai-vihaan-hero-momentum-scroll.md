# MSG: Hero momentum follow-up to site-wide smooth scrolling (#206)

- ID: `20261017T162117Z-sarosh-to-sai-vihaan-hero-momentum-scroll`
- From: sarosh
- To: sai, vihaan; cc adam, alan, srihith
- Kind: `integration` + `handoff`
- Timestamp (UTC): 2026-10-17T16:21:17Z
- Branch / commit / PR or issue link: `feat/sarosh/hero-momentum-scroll` at `dbbee6f`; PR #217
- Related subsystem(s): frontend (landing hero)

## Summary (facts)

The user asked for momentum scrolling on the hero page as well. #206 already
mounts `SmoothScroll` in the root layout, so mouse-wheel/trackpad scrolling on `/`
is already eased; this change does not duplicate or replace that.

This branch adds inertia to the hero's own scroll-linked motion:

- `frontend/components/hero.tsx` eases its `--scroll` value toward the page
  position, so the hero parallax, orb drift and content settle after the page
  stops rather than stopping exactly with the last wheel frame.
- `heroScrolled` / `heroPast` header state still comes from the real scroll
  position, so the header does not lag.
- Reduced-motion users keep the existing static hero with no animation loop.
- Global wheel handling, native scrollbar, keyboard, touch, anchors and every
  other route are unchanged.

## Tests executed

- `npm test` in `frontend`: **158 passed** (38 files), including new
  `tests/unit/hero-momentum.test.tsx` covering easing, immediate header state and
  reduced motion.
- `npm run lint`: pass.
- `npm run typecheck`: pass.
- Transport build was run locally only because the frontend package depends on
  `file:./transport`; no transport changes are in this PR.

## Action required by recipients

@SaiC123 @vihaankrishna100: please review PR #217 or flag overlap with active
frontend work. If the intent was only the site-wide `SmoothScroll` behavior from
#206, this is additive and can be dropped without touching that component.

## Evidence

- Files: `frontend/components/hero.tsx`,
  `frontend/tests/unit/hero-momentum.test.tsx`, `CHANGELOG.md`.
- PR #217 CI will run the normal frontend/backend/documentation gates.
