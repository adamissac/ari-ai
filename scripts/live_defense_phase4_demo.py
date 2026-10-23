#!/usr/bin/env python3
"""Print (and optionally drive) the Phase 4 owned-test enforcement demo.

This is not customer production. The adapter talks only to a loopback fixture.
RL / rules never execute without the independent authorization gate.

Usage (after `make dev` or a test API):

  export ARI_API=http://127.0.0.1:8000/api/v1
  export ARI_CSRF=...
  python scripts/live_defense_phase4_demo.py --print

Commands the operator runs:

  1. Register an owned_test application (UI Staging apps, or POST /projects/{id}/applications).
  2. Create a control grant for exact kinds on that app.
  3. Register a loopback control channel (port only). Copy the HMAC secret once.
  4. Start the fixture with that secret:
       OWNED_TEST_HMAC_SECRET=hkt_ctl_... uv run python -m backend.live_defense.owned_test_app --port 8099
  5. Authorize a temporary control from the Controls tab
     (POST /applications/{id}/control-authorizations). Analyst accept still does not execute.
  6. Worker jobs live_defense_execute then live_defense_verify probe real HTTP.
     Adapter HTTP 200 is not effectiveness.
  7. Rollback or wait for app-local TTL. Emergency stop rejects new controls
     and does not claim success until removal is verified.
"""

from __future__ import annotations

import argparse

COMMANDS = """
# Demo: owned-test Phase 4 (not production)

export ARI_API="${ARI_API:-http://127.0.0.1:8000/api/v1}"
# Session cookie + CSRF from a signed-in owner. Do not put secrets on argv in shared logs.

# 1. Register app (environment owned_test only)
# POST $ARI_API/projects/$PROJECT_ID/applications
# {"name":"payments-lite owned test","environment":"owned_test"}

# 2. Grant exact kinds
# POST $ARI_API/projects/$PROJECT_ID/control-grants
# {"application_id":"$APP_ID","allowed_kinds":["rate_limit","block_source","increase_logging","escalate"],"max_duration_s":300,"hourly_budget":5,"expires_at":null}

# 3. Register loopback channel; HMAC shown once
# POST $ARI_API/applications/$APP_ID/control-channel
# {"port":8099}

# 4. Fixture with the issued secret (loopback only)
OWNED_TEST_HMAC_SECRET="$HMAC" uv run python -m backend.live_defense.owned_test_app --port 8099

# 5. Authorize (separate from analyst review)
# POST $ARI_API/applications/$APP_ID/control-authorizations
# {"kind":"rate_limit","target":{"type":"route","value":"GET /payments/pay_fixture"},"duration_s":60,"max_requests":1,"rationale":"owned-test demo","live_policy_decision_id":null}

# 6. Worker applies + verifies with real requests
# GET $ARI_API/live-controls/$CONTROL_ID
# Probe: curl -i http://127.0.0.1:8099/payments/pay_fixture
# Second probe should be 429 when max_requests=1.

# 7. Rollback (success only after verify) or emergency stop
# POST $ARI_API/live-controls/$CONTROL_ID/rollback
# {"reason":"demo rollback"}
# POST $ARI_API/projects/$PROJECT_ID/emergency-stop
# {"application_id":"$APP_ID","note":"demo kill switch"}
""".strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 4 owned-test demo commands")
    parser.add_argument("--print", action="store_true", dest="show", help="print operator commands")
    args = parser.parse_args()
    if args.show:
        print(COMMANDS)
        return 0
    parser.print_help()
    print()
    print(COMMANDS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
