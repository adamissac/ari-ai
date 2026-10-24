# Probe check template review packet

A human security owner signs off by replacing `reviewed_by` in
`security_agents/checks/library.py` with their identity and recording the
`renderer_sha256` they reviewed. Any change to a renderer changes its hash and needs a new review.

Checklist for each template:

- [ ] The rendered module imports only json, decimal, datetime, fastapi and the package named by the recipe's app_factory (validated as package.module:callable).
- [ ] It uses only fixture identities and resource ids declared in the build recipe.
- [ ] It opens no sockets, spawns no processes and reads no environment or files outside the workspace.
- [ ] Its assertions state the expectation, so a failure means the expectation did not hold.
- [ ] Its side effects match the declared side_effect_class.
- [ ] The renderer rejects unknown or missing parameters and identical owner and other identities.

## access_control.ownership@1

- category: `access_control.ownership`; side effects: `read_only`
- current reviewed_by: `security-owner:pending-human-signoff`
- parameters: route_id, owner_identity, other_identity
- renderer_sha256: `9db6d770824e4a72be15cd34fbc80715c55c055217d02c4f5c69941f180323aa`
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


PATH = "/payments/pay_a1"
OWNER_HEADERS = {"Authorization": "Bearer fixture-token-alice"}
OTHER_HEADERS = {"Authorization": "Bearer fixture-token-bob"}
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
- renderer_sha256: `3adeaf3e12a1e924431796dacf0c8d7e1d17605aa371dce3024414f256421151`
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


CREATE_PATH = "/refunds"
READ_PATH = "/payments/pay_a1"
HEADERS = {"Authorization": "Bearer fixture-token-alice"}
BOUND = Decimal("120.00")
ACCUMULATED_FIELD = "refunded"
FULL_BODY = {"payment_id": "pay_a1", "amount": "120.00"}
EXTRA_BODY = {"payment_id": "pay_a1", "amount": "1.00"}


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

## access_control.authentication@1

- category: `access_control.authentication`; side effects: `read_only`
- current reviewed_by: `security-owner:pending-human-signoff`
- parameters: route_id, identity
- renderer_sha256: `c1280d58f85ae79934974924c387ea8150845c3dbc7d0f663d67251ae33754e1`
- sample parameters: `{"identity": "alice", "route_id": "payment_detail"}`
- rendered_sha256 (sample): `bed134ce73c11942471130cb2ccecdd8a469de24632016b3cce53b070ac87132`
- imports: decimal, fastapi, json, payments_lite (within allowlist: True)
- forbidden tokens in code: none

```python
"""Generated check: access_control.authentication@1
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


PATH = "/payments/pay_a1"
AUTH_HEADERS = {"Authorization": "Bearer fixture-token-alice"}
DENIED = [401, 403]


def test_unauthenticated_request_is_denied():
    resp = _client().get(PATH)
    RESULT["anon_status"] = resp.status_code
    RESULT["anon_leaked_body"] = resp.status_code == 200
    assert resp.status_code in DENIED, (
        f"expected one of {DENIED} for an unauthenticated request, observed {resp.status_code}"
    )


def test_authenticated_identity_retains_access():
    resp = _client().get(PATH, headers=AUTH_HEADERS)
    RESULT["identity_status"] = resp.status_code
    assert resp.status_code < 400, (
        f"authenticated identity lost legitimate access: {resp.status_code}"
    )
```

## access_control.role@1

- category: `access_control.role`; side effects: `ephemeral_target_only`
- current reviewed_by: `security-owner:pending-human-signoff`
- parameters: route_id, restricted_identity, permitted_identity
- renderer_sha256: `12a9bcd0d3f875b7bd0f7305e9b53ef8a0558f9fae0b2b4c237dc5047ebcea3c`
- sample parameters: `{"permitted_identity": "alice", "restricted_identity": "bob", "route_id": "create_refund"}`
- rendered_sha256 (sample): `3e839d7cb5c714c9f082ccaf84d4ec9c09d88559043038c6a734d0b61bbbb196`
- imports: decimal, fastapi, json, payments_lite (within allowlist: True)
- forbidden tokens in code: none

```python
"""Generated check: access_control.role@1
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


PATH = "/refunds"
METHOD = "post"
BODY = {"payment_id": "pay_a1", "amount": "120.00"}
RESTRICTED_HEADERS = {"Authorization": "Bearer fixture-token-bob"}
PERMITTED_HEADERS = {"Authorization": "Bearer fixture-token-alice"}
DENIED = [401, 403, 404]


def test_restricted_identity_is_denied():
    resp = _client().request(METHOD, PATH, json=BODY, headers=RESTRICTED_HEADERS)
    RESULT["restricted_status"] = resp.status_code
    RESULT["restricted_leaked_or_mutated"] = resp.status_code < 400
    assert resp.status_code in DENIED, (
        f"expected one of {DENIED} for a lower-privileged identity, observed {resp.status_code}"
    )


def test_permitted_identity_retains_access():
    resp = _client().request(METHOD, PATH, json=BODY, headers=PERMITTED_HEADERS)
    RESULT["permitted_status"] = resp.status_code
    assert resp.status_code < 400, f"permitted identity lost legitimate access: {resp.status_code}"
```
