# Probe check template review packet

A human security owner signs off by replacing `reviewed_by` in
`security_agents/checks/library.py` with their identity and recording the
`renderer_sha256` they reviewed. Any change to a renderer changes its hash and needs a new review.

Checklist for each template:

- [ ] The rendered module imports only json, decimal, fastapi and payments_lite.
- [ ] It uses only fixture identities and resource ids declared in the build recipe.
- [ ] It opens no sockets, spawns no processes and reads no environment or files outside the workspace.
- [ ] Its assertions state the expectation, so a failure means the expectation did not hold.
- [ ] Its side effects match the declared side_effect_class.
- [ ] The renderer rejects unknown or missing parameters and identical owner and other identities.

## access_control.ownership@1

- category: `access_control.ownership`; side effects: `read_only`
- current reviewed_by: `security-owner:pending-human-signoff`
- parameters: route_id, owner_identity, other_identity
- renderer_sha256: `d8aa32da22c9d55f98de9d19ccfdc77b2f439309ef320910d434fb8e733f1d09`
- sample parameters: `{"other_identity": "bob", "owner_identity": "alice", "route_id": "payment_detail"}`
- rendered_sha256 (sample): `edf41dbd1dce5f14c86d37e311020c082660c88d84534e71b15a7f697776a258`
- imports: decimal, fastapi, json, payments_lite (within allowlist: True)
- forbidden tokens in code: none

```python
"""Generated check: access_control.ownership@1
Rendered by security_agents.checks.library from reviewed template parameters.
Target is driven in-process through its own app factory; no sockets are opened.
"""

import json
from decimal import Decimal

from fastapi.testclient import TestClient

from payments_lite.app import create_app

RESULT = {}


def _client():
    return TestClient(create_app())


PATH = '/payments/pay_a1'
OWNER_HEADERS = {"Authorization": 'Bearer fixture-token-alice'}
OTHER_HEADERS = {"Authorization": 'Bearer fixture-token-bob'}
DENIED = [403, 404]


def test_owner_retains_access():
    resp = _client().get(PATH, headers=OWNER_HEADERS)
    RESULT["owner_status"] = resp.status_code
    assert resp.status_code == 200, f"owner lost legitimate access: {resp.status_code}"


def test_other_identity_is_denied():
    resp = _client().get(PATH, headers=OTHER_HEADERS)
    RESULT["other_status"] = resp.status_code
    RESULT["other_leaked_body"] = resp.status_code == 200
    assert resp.status_code in DENIED, (
        f"expected one of {DENIED} for a non-owner, observed {resp.status_code}"
    )
```

## input_validation.bounds@1

- category: `input_validation.bounds`; side effects: `ephemeral_target_only`
- current reviewed_by: `security-owner:pending-human-signoff`
- parameters: route_id, read_route_id, owner_identity, over_by
- renderer_sha256: `f849e25fbd746f08a44547b3b57335a730e90099d79556c31120a347aa4b7757`
- sample parameters: `{"over_by": "1.00", "owner_identity": "alice", "read_route_id": "payment_detail", "route_id": "create_refund"}`
- rendered_sha256 (sample): `60cdf74e814323158346001798f60210c32ddd387aa3cf7d4de4dc04b62786ed`
- imports: decimal, fastapi, json, payments_lite (within allowlist: True)
- forbidden tokens in code: none

```python
"""Generated check: input_validation.bounds@1
Rendered by security_agents.checks.library from reviewed template parameters.
Target is driven in-process through its own app factory; no sockets are opened.
"""

import json
from decimal import Decimal

from fastapi.testclient import TestClient

from payments_lite.app import create_app

RESULT = {}


def _client():
    return TestClient(create_app())


CREATE_PATH = '/refunds'
READ_PATH = '/payments/pay_a1'
HEADERS = {"Authorization": 'Bearer fixture-token-alice'}
BOUND = Decimal('120.00')
ACCUMULATED_FIELD = 'refunded'
FULL_BODY = {'payment_id': 'pay_a1', 'amount': '120.00'}
EXTRA_BODY = {'payment_id': 'pay_a1', 'amount': '1.00'}


def test_in_bounds_request_is_accepted():
    """A refund up to the bound is legitimate and must still work."""
    resp = _client().post(CREATE_PATH, json=FULL_BODY, headers=HEADERS)
    RESULT["in_bounds_status"] = resp.status_code
    assert resp.status_code < 400, f"legitimate in-bounds request rejected: {resp.status_code}"


def test_bound_is_enforced_across_requests():
    client = _client()
    first = client.post(CREATE_PATH, json=FULL_BODY, headers=HEADERS)
    RESULT["first_status"] = first.status_code
    assert first.status_code < 400, f"setup request rejected: {first.status_code}"
    second = client.post(CREATE_PATH, json=EXTRA_BODY, headers=HEADERS)
    RESULT["over_bound_status"] = second.status_code
    detail = client.get(READ_PATH, headers=HEADERS)
    accumulated = Decimal(str(detail.json()[ACCUMULATED_FIELD]))
    RESULT["accumulated"] = str(accumulated)
    RESULT["bound"] = str(BOUND)
    assert 400 <= second.status_code < 500, (
        f"expected 4xx once the accumulated total would exceed {BOUND}, "
        f"observed {second.status_code}"
    )
    assert accumulated <= BOUND, (
        f"invariant broken: accumulated {accumulated} exceeds the bound {BOUND}"
    )
```
