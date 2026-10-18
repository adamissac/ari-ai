# Srihith → Vihaan, Sai, Adam: night surface on every page but the landing

Branch `claude/wizardly-mccarthy-hni97r` (frontend only, no contract or backend change).

- **What changed.** Every page without a full-screen hero stage (`.hero-full`: the landing and
  the sign-in screens keep theirs) now uses the hero's ink + ember look at lower intensity.
  The landing page is unchanged.
- **How it works (please build on it):**
  - Tokens flip under `:root:not(:has(.hero-full))` at the end of `app/globals.css`.
    Anything written with `bg-panel`, `text-ink`, `border-line`, `text-muted` or the status
    colours follows automatically.
  - **If you need a surface that must stay dark, use `var(--color-night)`, not
    `var(--color-ink)`.** On night pages `--color-ink` is the light text colour. I switched
    the existing ink-as-background rules: `.hero-ink`, `.lab-now`, `.net-map`, `.graph-view`,
    `.lab-mode`, `.lab-key-dark`, `.pricing-card-dark` and the map/cut circles.
  - White pills carrying ink text (`.demo-tab[aria-selected]`, `.amap-btn`, `.amap-speeds`
    pressed, `.pricing-badge`) now use `--color-night` for their text.
  - Brand-coloured text on night is `--color-ember` (`#ff8a75`); `text-brand` and
    `text-accent` map to it there.
- **New pieces:**
  - `components/ambient.tsx` (fixed drifting light, grid and grain, with scroll parallax).
  - `useRevealOnScroll` (`Panel` rises once when first scrolled into view).
  - `Button` now carries `data-variant` and the class `.btn`.
  - `PageTitle` carries `.page-title` (blur-rise entrance).
  - `Loading` shows an ember pulse.
- **Sai (Lab):** `.lab-headline`, `.lab-score-card`, `.lab-step` and `.lab-replay-card` get
  dark glass on night, and `.lab-segment-btn[aria-pressed]` gets a glass pill. The teal
  network map is untouched.
- **Adam (demo):**
  - Light `.demo-chip-*` and `.demo-card` get their dark variants on night pages.
  - `body:has(.commit-stage)` now sits on the shared night background.
  - The footer still follows your rule: none on `/demo`.
- **Checks:** lint, typecheck, unit tests (night contrast asserted in `contrast.test.ts`), the
  `tests/e2e/stack.py` run and a production build. Results are in SESSION_HANDOFF.
