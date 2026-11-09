# ADR-0023: Security-agent testing for JavaScript/TypeScript repositories (proposed)

- Status: Proposed (owner review: Adam; security-boundary review required before step 3 ships)
- Date: 2026-11-01
- Context: The seven runtime agents test only Python/FastAPI apps. When the index has no
  HTTP entry points, the orchestrator runs the functional review and skips the agents
  (#683). Both pilot repositories are JavaScript:
  - `adamissac/mypypath` is static HTML plus Vercel functions in `api/`. Those functions
    use firebase-admin from `server/`, verify Firebase ID tokens, and are guarded by an
    824-line `firestore.rules`.
  - `adamissac/ascentmath` is Next.js App Router (`src/app/api/contact/route.ts`) with
    Firebase and a small `firestore.rules`.

  Four pieces are missing: route detection for JS/TS, a way to build and serve a Node app
  in the sandbox, test identities that the app's real auth accepts, and checks for
  Firestore rules, which on these apps are the main authorization boundary. Clients talk
  to Firestore directly, so the HTTP routes are not the main boundary.

## Decision

### 1. JS/TS route detection (code intelligence)

- `code_intelligence` parses `.js/.mjs/.cjs/.jsx/.ts/.tsx` with tree-sitter
  (`tree-sitter-javascript`, `tree-sitter-typescript`, pinned beside the Python grammar).
- It emits one `function` symbol per handler and `EntryPoint(kind=http_route)` records
  with the existing shared contract. There is no new contract field.
- Recognised conventions, all syntactic, each with a fixture test:

| Convention | Path rule | Methods |
|---|---|---|
| Next.js App Router | `app/**/route.(js\|ts)`, including under `src/` | each exported `GET`/`POST`/`PUT`/`PATCH`/`DELETE` |
| Next.js Pages API | `pages/api/**` | `default` export; methods from `req.method` comparisons, else `ANY` |
| Vercel functions | top-level `api/**/*.(js\|ts)` | `default` export; methods as above |
| Express / Router | `X.get('/p', …)` where `X` is assigned from `express()` or `express.Router()` | the call's verb |
| Cloud Functions | exported `onRequest(...)` / `functions.https.onRequest(...)` | `ANY`, path `/<exportName>` |

- File-system segments map to templates as follows: `[id]` becomes `{id}`, and
  `[...slug]` becomes `{slug}`.
- Auth signals go in `auth_dependencies`. A handler that reads `authorization` headers or
  calls `verifyIdToken` / `getServerSession` gets the matching signal.
- Anything else (dynamic route tables, custom servers) is not detected, and the
  provenance says so.

### 2. Node build recipe (`kind: "node_http"`)

`build_recipe.json` gains a second kind. It is repository content, so every field is
validated. Nothing in it reaches a shell. The platform chooses every command.

```json
{
  "recipe_version": 1,
  "kind": "node_http",
  "node": "22",
  "serve": {"adapter": "vercel_functions", "dir": "api"},
  "env": {"PYPATH_SCHOOL_CODE_CHECKS": "enabled",
          "PYPATH_FIREBASE_SERVICE_ACCOUNT": "$sandbox_service_account"},
  "firebase": {"project_id": "mypypath", "rules": "firestore.rules",
               "emulators": ["auth", "firestore"]},
  "identities": {"alice": {"uid": "sbx-alice", "email": "alice@sbx.test",
                           "email_verified": true}},
  "seed": [{"path": "users/sbx-alice", "data": {"role": "teacher"}}],
  "firestore_paths": [{"id": "user_doc", "path_template": "users/{uid}",
                       "owner_field": "uid"}],
  "routes": [{"id": "teacher_status", "method": "GET",
              "path_template": "/api/teacher-verification"}],
  "test_command": {"runner": "vitest", "args": ["run", "tests/rules"]}
}
```

- **`serve.adapter`** is a closed set of platform-owned launchers. There is no free-form
  start command.
  - `vercel_functions`: a ~100-line platform Node server. It mounts each `api/*` default
    export with Vercel's `req`/`res` helpers (`res.status().json()`, parsed JSON body).
  - `next`: `next build`, then `next start` (not implemented yet).
  - `express_module`: `{"module": "server/app.js", "export": "app"}`, listened on by the
    platform (not implemented yet).

  The launcher (`security_agents/sandbox/node_stack.mjs`) starts the emulators, seeds the
  identities and documents, and serves the adapter. It logs requests in uvicorn's
  access-log shape, so the existing `target_contact` evidence works unchanged.
- **`env`** values are literal strings, matched by `^[A-Za-z0-9 ._:/@-]{0,200}$`, or one
  platform placeholder.
  - `$sandbox_service_account` is a throwaway RSA service account generated per run. It
    is never a customer credential. With the emulator variables set, firebase-admin never
    calls Google.
  - Names that look like real secrets are refused when their value is a literal: the
    redactor's `*_KEY`, `*_SECRET` and `*_TOKEN` patterns, plus `GOOGLE_APPLICATION_CREDENTIALS`.
- **Identities** are Auth-emulator users created at sandbox start. Their `auth_header`
  is computed, not written in the recipe. It is `Bearer <unsigned emulator ID token>`,
  which the Auth emulator and firebase-admin (in emulator mode) accept, including
  `verifyIdToken(token, true)`. The check library keeps reading
  `recipe.identities[name].auth_header`, so the existing templates work unchanged.
- **`seed`** documents are written through the Firestore emulator's admin path
  (`Authorization: Bearer owner`), before the rules are evaluated for test identities.
- **`test_command`** names a runner from a closed set (`vitest`, `jest`) plus validated
  args. It runs with network `none`, except for loopback to the emulators. The sandbox
  entry runs it with a JSON reporter and reports in pytest's shape, plus a test-id audit,
  so Verify's "protected tests not collected" check applies to JS suites too. The hook
  audit is pytest-only.
- `backend/recipes.py` drafts this kind on connect (`backend/node_recipes.py`)
  when the repository has `package.json`, `package-lock.json`, and either explicit-GET
  parameterless `api/` routes or owner-scoped Firestore rules. The draft is deterministic,
  with no model call. Routes marked `ANY`, and routes with path parameters (which need
  fixture `resources`), are left out and listed in the PR notes. The draft is opened as
  the same setup PR. The owner merging it is the approval, as for Python.

### 3. Node sandbox runner

The boundary is unchanged: Vercel Sandbox microVM, deny-all egress, destroyed after the
run, no host credentials ([§4](../15_SECURITY_BOUNDARIES.md#4-sandbox-requirements)).

- **Base snapshot** (no repository code). Contents:
  - Node 22 and an OpenJDK 21 headless JRE.
  - Pinned `firebase-tools`, with emulator JARs pre-fetched by
    `firebase setup:emulators:firestore` and the auth emulator bundled.
  - Pinned `@firebase/rules-unit-testing` and `firebase` in a platform-owned directory.
  - The existing Python runner wheels.
  - Build egress allowlist: `registry.npmjs.org`, the emulator download host, and the
    current PyPI/Ubuntu hosts.
- **Dependency layer**, keyed by `sha256(package-lock.json)`. It runs in a builder that
  receives only `package.json` and `package-lock.json`.
  - The install command is `npm ci --ignore-scripts --no-audit --no-fund`, with egress
    to `registry.npmjs.org` only.
  - With `--ignore-scripts`, no repository code runs while egress is open.
  - A lockfile whose `resolved` URLs are not on `https://registry.npmjs.org/` is refused,
    so git and tarball dependencies fail closed.
  - Packages that need install scripts (native addons) are a documented limitation.
- **Run box** (deny-all egress). Steps, in this order:
  1. Start the emulators on loopback.
  2. Seed the identities and documents.
  3. Start the adapter on `127.0.0.1:8000`.
  4. Run the Python check runner against `SANDBOX_TARGET_URL`.
- The `http` check transport is allowed on the Vercel driver as well as Docker. Both
  provide a target reachable only inside the run boundary.
- **Rollout:** the Vercel path is opt-in (`SECURITY_AGENTS_NODE_ON_VERCEL=1`) until a live
  smoke on Vercel passes. Without the flag, production skips `node_http` targets with a
  label. Node is the official tarball, pinned by sha256 per architecture. firebase-tools
  checks the emulator JAR it fetches. Emulator JARs are read from
  `FIREBASE_EMULATORS_PATH`, so a run never downloads one.
- For local development without Docker, `LocalProcessDriver` can run the same flow
  behind its existing opt-in flag. Tests use real emulators: a local Java and the cached
  JAR are enough.

### 4. Which checks apply

- **HTTP, over the `http` transport.**
  - `authentication` (unauthenticated is denied, a signed-in identity keeps access) and
    `ownership`/BOLA (identity B requests A's `{id}`) apply as they are. They need a
    `GET` route with zero or one path parameter.
  - `bounds` and `role` change state. They stay refused over `http`
    (`side_effect_class` gate), as today.
- **Firestore rules.** These are new reviewed templates in the existing scope categories
  (`access_control.ownership` / `.authentication`), with side effect `ephemeral_target_only`
  (the per-run emulator is the ephemeral target). They are run by one platform-owned harness
  (`checks/firestore_harness.mjs`) on `@firebase/rules-unit-testing` against the run's
  emulator. The harness receives JSON parameters. The checks emit no generated code.
  - `firestore.owner_isolation`: the owner can `get` their doc at `path_template`.
    Another identity's `get` and `set` must fail (`assertFails`).
  - `firestore.unauthenticated_denied`: an unauthenticated context's `get` and `list`
    must fail.
  - `firestore.collection_enumeration`: `list` on the collection by a non-owner must fail.

  The verdict is deterministic, from the emulator's allow/deny outcomes. Only a
  `permission-denied` counts as denied; any other error is no verdict. The owner's `get` is
  a positive control: if it is denied (a server-only collection), the check is inconclusive,
  never a finding. A leak is a confirmed finding with the emulator's outcomes as evidence.
  `checks.list_templates` hides Firestore templates when the recipe has no
  `firestore_paths`, and HTTP templates when it has no `routes`.
- Firestore paths are not `EntryPoint`s. Scout's prompt lists the recipe's
  `firestore_paths` and the rules file, and Probe sees them as the `path_id`
  parameter values of `checks.list_templates`. The orchestrator stops skipping the agents
  when the index has HTTP entry points **or** the recipe declares `firestore_paths`.
- **Verify** re-runs the same template and parameters on the patched tree. For a rules
  patch, the emulator loads the patched `firestore.rules`. Verify also runs the
  recipe's `test_command` for the suite comparison.

## Consequences

- `docs/15_SECURITY_BOUNDARIES.md` §4 gains three rules: the dependency-layer rule
  (lockfile-only builder, `--ignore-scripts`, registry-only resolved URLs), the
  generated-service-account rule, and the emulator counting as the ephemeral target.
  Emulator state is per-run and destroyed with the box.
- Live Firebase projects are never contacted. Every Firebase call goes to loopback
  emulators. A recipe cannot name a real project credential.
- Delivery order, one PR each, each with real tests:
  1. This ADR, JS/TS route detection, and the orchestrator gate.
  2. Recipe kind, validation, emulator identities, and the Firestore harness, tested
     against a real emulator.
  3. The Node sandbox (local driver and Vercel base/dependency layers) with the
     `vercel_functions` adapter and the `http` transport.
  4. Recipe drafting on connect.

  The pilot then runs on `mypypath`.
- Known gaps:
  - Only syntactic route detection.
  - No install scripts.
  - The `next` adapter runs a full build inside the run's time limit.
  - Mutating HTTP checks stay out of scope.
