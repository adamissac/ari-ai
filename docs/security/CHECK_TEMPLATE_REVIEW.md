# Probe check template review packet

A human security owner signs off by replacing `reviewed_by` in
`security_agents/checks/library.py` with their identity and recording the
`renderer_sha256` they reviewed. Any change to a renderer changes its hash and needs a new review.

Checklist for each template:

- [ ] The rendered module imports only json, decimal, datetime, fastapi, pytest (to report a setup problem as skipped, never as a finding), threading and concurrent.futures (the race template) and the package named by the recipe's app_factory (validated as package.module:callable).
- [ ] It uses only fixture identities and resource ids declared in the build recipe.
- [ ] It opens no sockets, spawns no processes and reads no environment or files outside the workspace.
- [ ] Its assertions state the expectation, so a failure means the expectation did not hold.
- [ ] Its side effects match the declared side_effect_class.
- [ ] Harness templates only: the module starts the listed support file with `node` (no shell) and reads its JSON output; the support file reaches only the loopback Firestore emulator.
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


PATH = '/payments/pay_a1'
AUTH_HEADERS = {"Authorization": 'Bearer fixture-token-alice'}
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


PATH = '/refunds'
METHOD = 'post'
BODY = {'payment_id': 'pay_a1', 'amount': '120.00'}
RESTRICTED_HEADERS = {"Authorization": 'Bearer fixture-token-bob'}
PERMITTED_HEADERS = {"Authorization": 'Bearer fixture-token-alice'}
DENIED = [401, 403, 404]


def test_restricted_identity_is_denied():
    resp = _client().request(METHOD, PATH, json=BODY, headers=RESTRICTED_HEADERS)
    RESULT["restricted_status"] = resp.status_code
    RESULT["restricted_leaked_or_mutated"] = resp.status_code < 400
    assert resp.status_code in DENIED, (
        f"expected one of {DENIED} for a lower-privileged identity, "
        f"observed {resp.status_code}"
    )


def test_permitted_identity_retains_access():
    resp = _client().request(METHOD, PATH, json=BODY, headers=PERMITTED_HEADERS)
    RESULT["permitted_status"] = resp.status_code
    assert resp.status_code < 400, (
        f"permitted identity lost legitimate access: {resp.status_code}"
    )
```

## firestore.owner_isolation@1

- category: `access_control.ownership`; side effects: `ephemeral_target_only`
- current reviewed_by: `security-owner:pending-human-signoff`
- parameters: path_id, owner_identity, other_identity
- renderer_sha256: `53bb3f10ddb6fb870f9e5250407c9aa04769d7829000bde22c0651461811e1b6`
- sample parameters: `{"other_identity": "bob", "owner_identity": "alice", "path_id": "user_doc"}`
- rendered_sha256 (sample): `00c68e9e4f63512f4be64acd86e84d65d3f443ca76382fa6724b0ac4694e5d01`
- imports: json, os, pathlib, pytest, subprocess, tempfile (within allowlist: True)
- forbidden tokens in code: none

```python
"""Generated check: firestore.owner_isolation@1
Rendered by security_agents.checks.library from reviewed template parameters.
Runs the reviewed .sandbox/firestore_harness.mjs against the run's Firestore emulator,
which loads this workspace's own rules file. Only rules denials count as "denied".
"""

import json
import os
import pathlib
import subprocess
import tempfile

import pytest

PARAMS = {'project_id': 'demo-ari-sample', 'rules_path': 'firestore.rules', 'seed': [{'path': 'users/sbx-alice', 'data': {'sbx_seed': True}}], 'ops': [{'name': 'owner_get', 'op': 'get', 'path': 'users/sbx-alice', 'as': 'sbx-alice', 'claims': {}}, {'name': 'other_get', 'op': 'get', 'path': 'users/sbx-alice', 'as': 'sbx-bob', 'claims': {}}, {'name': 'other_set', 'op': 'set', 'path': 'users/sbx-alice', 'as': 'sbx-bob', 'claims': {}, 'data': {'sbx_probe': True}}]}
RESULT = {}


@pytest.fixture(scope="module")
def outcomes():
    here, work = pathlib.Path(__file__).parent, pathlib.Path(tempfile.mkdtemp())
    params, out = work / "firestore_params.json", work / "firestore_out.json"
    params.write_text(json.dumps({**PARAMS, "out": str(out)}))
    subprocess.run(
        ["node", str(here / "firestore_harness.mjs"), str(params)],
        check=True, timeout=120, cwd=os.getcwd(),
    )
    rows = {o["name"]: o for o in json.loads(out.read_text())["outcomes"]}
    RESULT["outcomes"] = rows
    broken = [r for r in rows.values() if r["allowed"] is None]
    if broken:  # an error is not evidence either way: fail the fixture, not the assertion
        raise RuntimeError(f"emulator errors, no verdict: {broken}")
    if rows["owner_get"]["allowed"] is not True:
        # Positive control: if the owner cannot read either, the path is server-only or does
        # not fit this template. Inconclusive, never a finding.
        raise RuntimeError("positive control failed: the owner cannot read this document; no verdict")
    return rows


def test_other_identity_is_denied(outcomes):
    leaked = [n for n in ("other_get", "other_set") if outcomes[n]["allowed"]]
    RESULT["other_leaked"] = leaked
    assert not leaked, f"rules allowed a different identity to {leaked} the owner's document"
```

Support file `firestore_harness.mjs` (reviewed with this template):

```js
// Reviewed Firestore-rules check harness (ADR-0023). Platform-owned, copied into the
// sandbox as `.sandbox/firestore_harness.mjs`; never generated, never model-authored.
//
//   node firestore_harness.mjs <params.json>
//
// Loads the workspace's own rules file into the run's Firestore emulator
// (FIRESTORE_EMULATOR_HOST) and records, for each operation in `ops`, whether the rules
// allowed it. The caller compares the outcomes with the expectation; this file decides
// nothing. Packages come from the platform directory ARI_NODE_DIR, not from the target.
import { readFileSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { join } from 'node:path';

const params = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const require = createRequire(join(process.env.ARI_NODE_DIR, 'package.json'));
const { initializeTestEnvironment } = require('@firebase/rules-unit-testing');
const { doc, getDoc, setDoc, collection, getDocs, limit, query } = require('firebase/firestore');

const [host, port] = (process.env.FIRESTORE_EMULATOR_HOST || '').split(':');
if (host !== '127.0.0.1' && host !== 'localhost') throw new Error('emulator must be on loopback');

const env = await initializeTestEnvironment({
  projectId: params.project_id,
  firestore: { host, port: Number(port), rules: readFileSync(params.rules_path, 'utf8') },
});
const outcomes = [];
try {
  await env.clearFirestore();
  // Seed with rules disabled: the documents a real owner would already have.
  await env.withSecurityRulesDisabled(async (ctx) => {
    for (const s of params.seed) await setDoc(doc(ctx.firestore(), s.path), s.data);
  });
  for (const op of params.ops) {
    const db = (op.as === null ? env.unauthenticatedContext() : env.authenticatedContext(op.as, op.claims || {})).firestore();
    let allowed;
    let error = null;
    try {
      if (op.op === 'get') await getDoc(doc(db, op.path));
      else if (op.op === 'set') await setDoc(doc(db, op.path), op.data, { merge: true });
      else if (op.op === 'list') await getDocs(query(collection(db, op.path), limit(5)));
      else throw new Error(`unknown op ${op.op}`);
      allowed = true;
    } catch (e) {
      // Only a rules denial counts as "denied"; anything else is an error, not evidence.
      if (e && e.code === 'permission-denied') allowed = false;
      else { allowed = null; error = String(e && e.message || e).slice(0, 300); }
    }
    outcomes.push({ name: op.name, op: op.op, path: op.path, as: op.as, allowed, error });
  }
} finally {
  await env.cleanup();
}
writeFileSync(params.out, JSON.stringify({ outcomes }, null, 2));
```

## firestore.unauthenticated_denied@1

- category: `access_control.authentication`; side effects: `ephemeral_target_only`
- current reviewed_by: `security-owner:pending-human-signoff`
- parameters: path_id, owner_identity
- renderer_sha256: `60780821f8a3c0a72df435532d5c932b3e2e747935e341d506a66053a90b000b`
- sample parameters: `{"owner_identity": "alice", "path_id": "user_doc"}`
- rendered_sha256 (sample): `1082b4fe40ee580088909ea264122d8d34eef109fce7cbad68ece4aa9d0a4e85`
- imports: json, os, pathlib, pytest, subprocess, tempfile (within allowlist: True)
- forbidden tokens in code: none

```python
"""Generated check: firestore.unauthenticated_denied@1
Rendered by security_agents.checks.library from reviewed template parameters.
Runs the reviewed .sandbox/firestore_harness.mjs against the run's Firestore emulator,
which loads this workspace's own rules file. Only rules denials count as "denied".
"""

import json
import os
import pathlib
import subprocess
import tempfile

import pytest

PARAMS = {'project_id': 'demo-ari-sample', 'rules_path': 'firestore.rules', 'seed': [{'path': 'users/sbx-alice', 'data': {'sbx_seed': True}}], 'ops': [{'name': 'owner_get', 'op': 'get', 'path': 'users/sbx-alice', 'as': 'sbx-alice', 'claims': {}}, {'name': 'anon_get', 'op': 'get', 'path': 'users/sbx-alice', 'as': None}, {'name': 'anon_list', 'op': 'list', 'path': 'users', 'as': None}]}
RESULT = {}


@pytest.fixture(scope="module")
def outcomes():
    here, work = pathlib.Path(__file__).parent, pathlib.Path(tempfile.mkdtemp())
    params, out = work / "firestore_params.json", work / "firestore_out.json"
    params.write_text(json.dumps({**PARAMS, "out": str(out)}))
    subprocess.run(
        ["node", str(here / "firestore_harness.mjs"), str(params)],
        check=True, timeout=120, cwd=os.getcwd(),
    )
    rows = {o["name"]: o for o in json.loads(out.read_text())["outcomes"]}
    RESULT["outcomes"] = rows
    broken = [r for r in rows.values() if r["allowed"] is None]
    if broken:  # an error is not evidence either way: fail the fixture, not the assertion
        raise RuntimeError(f"emulator errors, no verdict: {broken}")
    if rows["owner_get"]["allowed"] is not True:
        # Positive control: if the owner cannot read either, the path is server-only or does
        # not fit this template. Inconclusive, never a finding.
        raise RuntimeError("positive control failed: the owner cannot read this document; no verdict")
    return rows


def test_unauthenticated_request_is_denied(outcomes):
    leaked = [n for n in ("anon_get", "anon_list") if outcomes[n]["allowed"]]
    RESULT["anon_leaked"] = leaked
    assert not leaked, f"rules allowed an unauthenticated client to {leaked}"
```

Support file `firestore_harness.mjs` (reviewed with this template):

```js
// Reviewed Firestore-rules check harness (ADR-0023). Platform-owned, copied into the
// sandbox as `.sandbox/firestore_harness.mjs`; never generated, never model-authored.
//
//   node firestore_harness.mjs <params.json>
//
// Loads the workspace's own rules file into the run's Firestore emulator
// (FIRESTORE_EMULATOR_HOST) and records, for each operation in `ops`, whether the rules
// allowed it. The caller compares the outcomes with the expectation; this file decides
// nothing. Packages come from the platform directory ARI_NODE_DIR, not from the target.
import { readFileSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { join } from 'node:path';

const params = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const require = createRequire(join(process.env.ARI_NODE_DIR, 'package.json'));
const { initializeTestEnvironment } = require('@firebase/rules-unit-testing');
const { doc, getDoc, setDoc, collection, getDocs, limit, query } = require('firebase/firestore');

const [host, port] = (process.env.FIRESTORE_EMULATOR_HOST || '').split(':');
if (host !== '127.0.0.1' && host !== 'localhost') throw new Error('emulator must be on loopback');

const env = await initializeTestEnvironment({
  projectId: params.project_id,
  firestore: { host, port: Number(port), rules: readFileSync(params.rules_path, 'utf8') },
});
const outcomes = [];
try {
  await env.clearFirestore();
  // Seed with rules disabled: the documents a real owner would already have.
  await env.withSecurityRulesDisabled(async (ctx) => {
    for (const s of params.seed) await setDoc(doc(ctx.firestore(), s.path), s.data);
  });
  for (const op of params.ops) {
    const db = (op.as === null ? env.unauthenticatedContext() : env.authenticatedContext(op.as, op.claims || {})).firestore();
    let allowed;
    let error = null;
    try {
      if (op.op === 'get') await getDoc(doc(db, op.path));
      else if (op.op === 'set') await setDoc(doc(db, op.path), op.data, { merge: true });
      else if (op.op === 'list') await getDocs(query(collection(db, op.path), limit(5)));
      else throw new Error(`unknown op ${op.op}`);
      allowed = true;
    } catch (e) {
      // Only a rules denial counts as "denied"; anything else is an error, not evidence.
      if (e && e.code === 'permission-denied') allowed = false;
      else { allowed = null; error = String(e && e.message || e).slice(0, 300); }
    }
    outcomes.push({ name: op.name, op: op.op, path: op.path, as: op.as, allowed, error });
  }
} finally {
  await env.cleanup();
}
writeFileSync(params.out, JSON.stringify({ outcomes }, null, 2));
```

## firestore.collection_enumeration@1

- category: `access_control.ownership`; side effects: `ephemeral_target_only`
- current reviewed_by: `security-owner:pending-human-signoff`
- parameters: path_id, owner_identity, other_identity
- renderer_sha256: `0c52171f74f5ea4df8d7453b854eec032e8947583201dab27904057f3f78f657`
- sample parameters: `{"other_identity": "bob", "owner_identity": "alice", "path_id": "user_doc"}`
- rendered_sha256 (sample): `edfb51a961abe1b2c1362528bc1297c268e9241b66a7db96c4f9ef8495709fa1`
- imports: json, os, pathlib, pytest, subprocess, tempfile (within allowlist: True)
- forbidden tokens in code: none

```python
"""Generated check: firestore.collection_enumeration@1
Rendered by security_agents.checks.library from reviewed template parameters.
Runs the reviewed .sandbox/firestore_harness.mjs against the run's Firestore emulator,
which loads this workspace's own rules file. Only rules denials count as "denied".
"""

import json
import os
import pathlib
import subprocess
import tempfile

import pytest

PARAMS = {'project_id': 'demo-ari-sample', 'rules_path': 'firestore.rules', 'seed': [{'path': 'users/sbx-alice', 'data': {'sbx_seed': True}}], 'ops': [{'name': 'owner_get', 'op': 'get', 'path': 'users/sbx-alice', 'as': 'sbx-alice', 'claims': {}}, {'name': 'other_list', 'op': 'list', 'path': 'users', 'as': 'sbx-bob', 'claims': {}}]}
RESULT = {}


@pytest.fixture(scope="module")
def outcomes():
    here, work = pathlib.Path(__file__).parent, pathlib.Path(tempfile.mkdtemp())
    params, out = work / "firestore_params.json", work / "firestore_out.json"
    params.write_text(json.dumps({**PARAMS, "out": str(out)}))
    subprocess.run(
        ["node", str(here / "firestore_harness.mjs"), str(params)],
        check=True, timeout=120, cwd=os.getcwd(),
    )
    rows = {o["name"]: o for o in json.loads(out.read_text())["outcomes"]}
    RESULT["outcomes"] = rows
    broken = [r for r in rows.values() if r["allowed"] is None]
    if broken:  # an error is not evidence either way: fail the fixture, not the assertion
        raise RuntimeError(f"emulator errors, no verdict: {broken}")
    if rows["owner_get"]["allowed"] is not True:
        # Positive control: if the owner cannot read either, the path is server-only or does
        # not fit this template. Inconclusive, never a finding.
        raise RuntimeError("positive control failed: the owner cannot read this document; no verdict")
    return rows


def test_collection_cannot_be_enumerated(outcomes):
    RESULT["other_listed"] = outcomes["other_list"]["allowed"]
    assert outcomes["other_list"]["allowed"] is False, "rules let another identity list the collection"
```

Support file `firestore_harness.mjs` (reviewed with this template):

```js
// Reviewed Firestore-rules check harness (ADR-0023). Platform-owned, copied into the
// sandbox as `.sandbox/firestore_harness.mjs`; never generated, never model-authored.
//
//   node firestore_harness.mjs <params.json>
//
// Loads the workspace's own rules file into the run's Firestore emulator
// (FIRESTORE_EMULATOR_HOST) and records, for each operation in `ops`, whether the rules
// allowed it. The caller compares the outcomes with the expectation; this file decides
// nothing. Packages come from the platform directory ARI_NODE_DIR, not from the target.
import { readFileSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { join } from 'node:path';

const params = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const require = createRequire(join(process.env.ARI_NODE_DIR, 'package.json'));
const { initializeTestEnvironment } = require('@firebase/rules-unit-testing');
const { doc, getDoc, setDoc, collection, getDocs, limit, query } = require('firebase/firestore');

const [host, port] = (process.env.FIRESTORE_EMULATOR_HOST || '').split(':');
if (host !== '127.0.0.1' && host !== 'localhost') throw new Error('emulator must be on loopback');

const env = await initializeTestEnvironment({
  projectId: params.project_id,
  firestore: { host, port: Number(port), rules: readFileSync(params.rules_path, 'utf8') },
});
const outcomes = [];
try {
  await env.clearFirestore();
  // Seed with rules disabled: the documents a real owner would already have.
  await env.withSecurityRulesDisabled(async (ctx) => {
    for (const s of params.seed) await setDoc(doc(ctx.firestore(), s.path), s.data);
  });
  for (const op of params.ops) {
    const db = (op.as === null ? env.unauthenticatedContext() : env.authenticatedContext(op.as, op.claims || {})).firestore();
    let allowed;
    let error = null;
    try {
      if (op.op === 'get') await getDoc(doc(db, op.path));
      else if (op.op === 'set') await setDoc(doc(db, op.path), op.data, { merge: true });
      else if (op.op === 'list') await getDocs(query(collection(db, op.path), limit(5)));
      else throw new Error(`unknown op ${op.op}`);
      allowed = true;
    } catch (e) {
      // Only a rules denial counts as "denied"; anything else is an error, not evidence.
      if (e && e.code === 'permission-denied') allowed = false;
      else { allowed = null; error = String(e && e.message || e).slice(0, 300); }
    }
    outcomes.push({ name: op.name, op: op.op, path: op.path, as: op.as, allowed, error });
  }
} finally {
  await env.cleanup();
}
writeFileSync(params.out, JSON.stringify({ outcomes }, null, 2));
```

## input_validation.concurrent_bound@1

- category: `input_validation.bounds`; side effects: `ephemeral_target_only`
- current reviewed_by: `security-owner:pending-human-signoff`
- parameters: route_id, read_route_id, owner_identity, parallel
- renderer_sha256: `9a3f425f549940429aefb72ea395885b6d6dca762ca94e46ec851c35f3239a06`
- sample parameters: `{"owner_identity": "alice", "parallel": 8, "read_route_id": "payment_detail", "route_id": "create_refund"}`
- rendered_sha256 (sample): `7be1a03f1e2890bf2575350d052fed6a9c3927dec198a80f77ba15d31e90b6c0`
- imports: concurrent, decimal, fastapi, json, payments_lite, pytest, threading (within allowlist: True)
- forbidden tokens in code: none

```python
"""Generated check: input_validation.concurrent_bound@1
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

import threading

import pytest
from concurrent.futures import ThreadPoolExecutor

CREATE_PATH = '/refunds'
READ_PATH = '/payments/pay_a1'
HEADERS = {"Authorization": 'Bearer fixture-token-alice'}
BODY = {'payment_id': 'pay_a1', 'amount': '72.00'}
BOUND = Decimal('120.00')
AMOUNT = Decimal('72.00')
PARALLEL = 8
FIELD_KIND = 'accumulated_field'
FIELD = 'refunded'


def _read_value(client):
    resp = client.get(READ_PATH, headers=HEADERS)
    if resp.status_code != 200 or FIELD not in resp.json():
        # The owner cannot read its own resource: a setup problem, not evidence.
        pytest.skip(f"read-back failed: {resp.status_code}")
    return Decimal(str(resp.json()[FIELD]))


def test_bound_holds_under_concurrent_requests():
    client = _client()
    barrier = threading.Barrier(PARALLEL)

    def one(_):
        barrier.wait(timeout=30)
        return client.post(CREATE_PATH, json=BODY, headers=HEADERS).status_code

    with ThreadPoolExecutor(PARALLEL) as pool:
        statuses = list(pool.map(one, range(PARALLEL)))
    accepted = sum(1 for s in statuses if s < 400)
    value = _read_value(client)
    moved = accepted * AMOUNT
    expected = BOUND - moved if FIELD_KIND == "balance_field" else moved
    RESULT.update(statuses=statuses, accepted=accepted, moved=str(moved), value=str(value))
    if accepted == 0:
        # Not evidence either way: the request itself is rejected (wrong body, auth, amount).
        pytest.skip(f"no concurrent request was accepted: {statuses}")
    assert moved <= BOUND, (
        f"{accepted} concurrent requests of {AMOUNT} accepted against a bound of {BOUND}"
    )
    assert value == expected, (
        f"lost update: {accepted} accepted requests should leave {FIELD}={expected}, "
        f"observed {value}"
    )
```

## input_validation.destination@1

- category: `input_validation.bounds`; side effects: `ephemeral_target_only`
- current reviewed_by: `security-owner:pending-human-signoff`
- parameters: route_id, read_route_id, owner_identity, destination_identity
- renderer_sha256: `1754a23332fbb085b7a31d013179f75d82d843831b4f800fba8149e21bd924ac`
- sample parameters: `{"owner_identity": "alice", "read_route_id": "payment_detail", "route_id": "sample_payout"}`
- rendered_sha256 (sample): `c599f9a0c4f16f8cd3b32481b34a49840e5c318a98ccaa5aff7b3cdad10a0fd5`
- imports: decimal, fastapi, json, payments_lite, pytest (within allowlist: True)
- forbidden tokens in code: none

```python
"""Generated check: input_validation.destination@1
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

import pytest

CREATE_PATH = '/payouts'
READ_PATH = '/payments/pay_a1'
HEADERS = {"Authorization": 'Bearer fixture-token-alice'}
BODY = {'payment_id': 'pay_a1', 'to': 'ari-probe-nonexistent-destination', 'amount': '1.00'}
FIELD = 'refunded'


def _read_value(client):
    resp = client.get(READ_PATH, headers=HEADERS)
    if resp.status_code != 200 or FIELD not in resp.json():
        # The owner cannot read its own resource: a setup problem, not evidence.
        pytest.skip(f"read-back failed: {resp.status_code}")
    return Decimal(str(resp.json()[FIELD]))


def test_invalid_destination_is_rejected_and_moves_nothing():
    client = _client()
    before = _read_value(client)
    resp = client.post(CREATE_PATH, json=BODY, headers=HEADERS)
    after = _read_value(client)
    RESULT.update(status=resp.status_code, before=str(before), after=str(after))
    assert after == before, f"{FIELD} changed from {before} to {after} for an invalid destination"
    assert 400 <= resp.status_code < 500, (
        f"expected 4xx for an invalid destination, observed {resp.status_code}"
    )
```
