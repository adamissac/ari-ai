# live-defense-target ("Lumen Shop", owned test application)

The only system Ari's Live Defense acts on during the demo. It runs on this machine,
serves a sign-in and an items route, reports its own security telemetry to Ari with an
ingest token, and exposes a signed control API (`/ari/controls`) through which Ari applies,
reads and removes reversible, expiring controls. Owner notifications arrive at
`/ari/notifications`; `GET /ari/state` shows active controls, received notifications and
telemetry delivery counters.

Traffic marked `X-Ari-Test-Traffic: 1` is reported as `controlled_test`. With
`TRUST_FORWARDED=1` (default, test only) the client address is taken from
`X-Forwarded-For`, so the demo uses RFC 5737 documentation addresses (203.0.113.0/24).

Start it through `scripts/live_defense_demo.py` (see `docs/runbooks/LIVE_DEFENSE_DEMO.md`).
