# Sai → all: landing hero ant colony

The landing hero now has a decorative ant colony on a canvas behind the headline (`frontend/components/ant-colony.tsx`, enabled with `<HeroStage colony>` on the home page only; the sign-in stage is unchanged).

- It starts with one scout ant leaving an ember-glow nest on the right and laying a dotted pheromone trail in a figure-eight.
- Followers join at a quickening pace, up to 10 on phones and 34 on large screens. At half size a second scout opens a looping ring trail.
- The ants have a tripod leg gait and flicking antennae, and they step around the cursor.
- The animation pauses off screen and in background tabs. Reduced motion gets one static frame.
- Verified in headless Chrome at 1440×900 and 390×844: 60 fps with the full colony and no horizontal scroll. Unit tests cover the trail geometry, constant walking speed, colony size and spawn pacing.

Owner: Sai (frontend). No other hero styles changed.
