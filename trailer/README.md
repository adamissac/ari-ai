# Ari trailer

90 s website trailer, built in code (HTML + springs, rendered frame by frame in headless Chromium).

- **Watch / embed:** `renders/ari-trailer-1080p.mp4` (1080p60 H.264 + AAC, -14 LUFS) and `renders/ari-trailer-poster.jpg`
- **Film:** `film/act1.js` … `film/act5.js` (scenes), `film/kit.js` (Ari's fonts, colours, ant colony, windows), `timeline.json` (beats, marks, SFX, music)
- **Real UI:** `assets/cap/` are captures of the demo console and Defense Lab (`scripts/capture-ari.mjs`, `scripts/capture-replay.mjs` against a local `NEXT_PUBLIC_DEMO_ONLY=1` build)

## Re-render
```sh
npm i && pip install numpy scipy soundfile librosa pillow   # plus ffmpeg and Playwright's Chromium
python3 scripts/music.py && node scripts/sync.mjs && node scripts/sfx.mjs && python3 scripts/mix.py
node scripts/render.mjs --at 12.5                 # a still → review/stills
node scripts/render.mjs --draft                   # 30 fps preview → renders/draft_16x9.mp4
node scripts/render.mjs --range 0,45 && node scripts/render.mjs --range 45,90 && sh scripts/finish.sh   # final
```
Edit copy or timing in the act files, then re-render. Everything is a pure function of time, so any range can be re-rendered and spliced (`scripts/splice.sh`).

Embed example:
```html
<video src="/trailer/ari-trailer-1080p.mp4" poster="/trailer/ari-trailer-poster.jpg" controls playsinline preload="metadata"></video>
```
