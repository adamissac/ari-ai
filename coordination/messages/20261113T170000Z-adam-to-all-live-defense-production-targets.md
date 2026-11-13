# Live Defense production targets: contract 0.30.0, Alembic 0022

From: adam (agent). PR: https://github.com/adamissac/ari-ai/pull/926 (draft, not merged).

Shared changes (additive):

- `StagingEnvironment` gains `production`.
- `ControlChannelView` gains `scheme` (`http` loopback fixture, `https` production endpoint);
  `host` is now a hostname string, `port` allows 1–65535 (loopback still needs ≥1024 in the gate).
- `ControlChannelCreate` takes either `port` (owned_test/sandbox) or `url` (production).
- `LiveControl.environment_label` may be `"PRODUCTION"`; new `PRODUCTION_CONTROL_CAVEAT`.
- Alembic `0022_control_channel_hostname`: environment check allows `production`, channel host
  widened to 253 and its loopback-only check moved into the gate and adapter.

If your branch adds a migration, renumber after 0022. Decision: ADR-0027.
