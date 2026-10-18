"""Live autonomous defense (docs/LIVE_AUTONOMOUS_DEFENSE_PLAN.md).

Pure parts: ``state`` (lifecycle), ``authorize`` (independent gate), ``policy`` (RL with a
recorded deterministic floor), ``monitoring.detect`` (rules). Effectful parts: ``engine``
(jobs), ``adapters`` (signed control calls), ``notify`` (signed webhooks), ``netguard``
(SSRF-safe outbound HTTP) and ``vault`` (Fernet at rest).
"""
