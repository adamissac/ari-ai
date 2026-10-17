# Local typography assets

Unmodified Latin WOFF2 files from Fontsource packages5.3.0, bundled under the
included SIL Open Font Licenses. `SOURCES.json` records package versions, source
tarball integrity and each file's SHA-256. No package is added to runtime deps.

Inter400–600, Space Grotesk500–700 and IBM Plex Mono400/500/600 preserve the existing
families, weights and CSS variables. `next/font/local` emits same-origin assets;
there is no build-time or browser-time font-service request. The local-font unit
test checks licenses, WOFF2 headers and checksums. Dependency installation still
requires its usual npm cache/registry; the font build itself needs no network.

Chakra Petch Latin 700 (Google Fonts family, unmodified Fontsource 5.3.0 asset)
is bundled exclusively for `.ari-wordmark-text`. The existing text families and
weights are unchanged; the additional OFL license and checksum are recorded here.
