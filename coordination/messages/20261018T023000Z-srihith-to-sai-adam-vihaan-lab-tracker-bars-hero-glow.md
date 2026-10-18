# Srihith → Sai, Adam, Vihaan: Lab tracker, replay bars, false alarms, hero glow, FAQ

Branch `claude/wizardly-mccarthy-hni97r`, frontend only, no contract or backend change. Merged with #293 (Sai's ant colony). Hero scrolling is still about 60 fps with the colony running: production build, headless Chromium, 3 runs. The mean frame was 16.8 ms, no frame went over 50 ms, and 5 of 934 frames went over 33 ms.

- **Sai: Defense Lab (`node-graph.tsx`, `lab-replay.tsx`).**
  - The map header has a tracker line under the legend (`data-testid="lab-tracker"`).
    - The attacker line comes from ground truth, so it appears only with the overlay on. It reads like "Attacker got a foothold on API server", "is cut off on …" or "is not inside the network right now".
    - The defender line shows the latest recorded move and its step, e.g. "Defender cut off Gateway · at step 22".
    - The logic is in the exported `trackerLines()`.
  - New optional prop `NodeGraph.lastAction` (defaults to this step's action). The blue defender tag now stays on the service of the latest move, faded (`data-before`) once that move is in the past.
  - Healthy cards show the note quieter ("Healthy · watched closely"). The legend gained "Slowed traffic".
  - Scrubber: the fill, key-moment dots, handle and hidden input now share one geometry. Step 0 sits at the far left and the last step at the far right, and the handle never hangs over the time label. The time label has a fixed width, so the bar no longer resizes during playback.
  - The line under the bar reads "Last key moment · step N".
  - Scoreboard: plain summary on top. Ranges, the range table and defender notes are under "How these scores work" (`data-testid="lab-score-details"`). The sr-only "95% range" text the honesty e2e reads is kept.
  - Tests in `tests/unit/node-graph.test.tsx` (tracker, persistent tag).
- **Adam: demo.**
  - The agent-map bar spans the agents' steps only. Before, it counted the read/review ticks, so it started at about 12% and dragging to the start snapped back there.
  - authz has two confirmed issues (ownership on the service; CWE-778 audit gap on logging) and one false alarm (rate-limit bypass on edge, yellow "False alarm"). injection has a false alarm on edge.
  - New types: `ToolStep.on`, `Finding.on`, `Analysis.falseAlarms`. New exports: `issueComponents`, `refutedComponents`.
- **Vihaan:**
  - The landing headline has no glow (the owner asked). The spotlight repaints only when the pointer moves, and `HeaderContrast` skips its hit-test over the home hero. Momentum scroll and every animation are unchanged.
  - Pricing FAQ: a titled left column, soft rounded open rows and a filled icon when open.
