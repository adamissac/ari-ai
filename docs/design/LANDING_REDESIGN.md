# Landing design study and redesign

Reference: https://kairo.security/ and the owner-provided screenshots.

The public page uses oversized technical branding, compact monospaced navigation,
contrasting editorial sections, illustrative technical diagrams and a grainy,
illuminated footer. Ari reimplements those visual principles with its own supplied
ant, local wordmark font, warm palette, product copy and valid navigation. No Kairo
logos, proprietary imagery or business/performance claims are imported.

The reference was inspected through its public HTML and supplied screenshots. The
connected-browser tools were unavailable in this session; no new capture of the
live Kairo page is claimed. Ari desktop/mobile screenshots were captured through
its Playwright suite and inspected during development.

## Readability changes

- The three problem statements stay visible together.
- Process explanations use keyboard-accessible tabs and a Next control. Selection
  stays put while scrolling; there is no autoplay or scroll-triggered content swap.
- The finding walkthrough has explicit step controls.
- Landing-page wheel input bounds a single flick and accumulated momentum. Native
  touch, keyboard, nested scrollers, pinch zoom and reduced-motion behavior remain.
- Console scrolling retains its existing behavior. The video still has its
  deliberate landing and explicit Continue exploring control.
- Illustration provenance labels remain visible; no synthetic figures are
  presented as recorded assessments.

## Visual changes

An editorial hero adds explanatory copy and clearer action hierarchy. The process
panel combines a restrained orbital diagram and legible code illustration with a
persistent text column. The full-bleed footer uses Ari's own ant and wordmark, an
etched scale, fine grain, a softly lit horizon and useful navigation. All assets
and fonts are local; no animation or image-generation service is required.
