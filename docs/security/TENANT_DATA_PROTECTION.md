# Tenant Data Protection — threat model, data-flow inventory, verified controls

Status: **implemented** unless marked *proposed* / *future*. Every control in
the matrix links to executable test evidence. Audience: security review,
enterprise customers, and the six-agent build team.

Related docs: `docs/15_SECURITY_BOUNDARIES.md`, `docs/security/NIST_INCIDENT_HANDLING.md`,
pilot disclosure `docs/pilot/DATA_HANDLING.md` (customer-facing, separate owner).

---

## 1. Threat model

**Protected asset:** private source code belonging to one customer org
("tenant") and everything derived from it (indexed payloads, prompts,
transcripts, artifacts, agent memory, assessments, findings, patches).

**Actors**

| Actor | Trust |
|---|---|
| Tenant member (member/owner role) | Reads own tenant's data; owner also mutates |
| Tenant viewer | Read-only inside own tenant |
| Another tenant's authenticated user (Eve) | **Untrusted** — must get 404s, never data, even knowing every ID |
| Unauthenticated client | 401 on all project surfaces |
| Repository content itself | Untrusted input (prompt injection); can never grant permissions |
| Operator (DB/host access) | Trusted but auditable |
| Anthropic API | External processor — see §7 |
| GitHub App | Credential issuer — see §5 |

**Trust boundaries**

1. HTTP API → org-membership check (`require_project`) before any resource access.
2. Storage accessors (`PostgresPayloadStore`, `PostgresMemoryStore`,
   `ArtifactStore` routes) re-validate tenancy against the DB, not the caller's claim.
3. Row-level security on the source-content tables (defense in depth, §6).
4. Worker/sandbox: untrusted code executes only in the sandbox, never on the host.
5. External calls: GitHub (installation tokens), Anthropic (redacted prompts).

**Out of scope (accepted):** a malicious *operator* with production DB/shell
access can read anything — mitigated by auditability and least-access ops
practice, documented in §9.

---

## 2. Private-code data-flow inventory

**Ari does store source code — not "metadata only".**

| Stage | What is stored | Where | Lifetime | Who/what can read |
|---|---|---|---|---|
| GitHub fetch | Bare clone of the connected repo at an exact commit | `SECURITY_WORKDIR/repos/{repo_id}.git` on the worker host | Until `purge_project` — **no TTL today** | Worker process only |
| Checkout auth | Installation token (see §5) | Process env only, never argv/git config/logs | ~50 min cache | Nobody — never persisted |
| Indexing | Parsed file payloads (BYTEA, ≤64 MiB/key) | `index_payloads` keyed by full SnapshotRef | Until purge | Only transactions scoped to that tenant (RLS §6) |
| Index registry | Snapshot rows/stats | `index_snapshots`, `snapshots` | Until purge | Same |
| Prompts | Repo code context (bounded context pack) | Sent to Anthropic per call | Provider-side per API terms | Anthropic only |
| Transcripts | Full LLM conversation incl. code context | `artifacts` (kind `llm_transcript`), redacted before storage | Until purge | Tenant members via `GET /artifacts/{id}` |
| Artifacts | diffs, logs, reports, webhook payloads | `artifacts` rows + content-addressed files under `ARTIFACT_STORE_URI` | Until purge | Members; `project_id NULL` artifacts unreadable by anyone |
| Findings/assessments | Evidence spans, hypotheses, patches | `findings`, `finding_records`, `patch_candidates`, `verification_results`, `assessments`, `agent_runs`, `assessment_events` | Until purge | Tenant members |
| Agent memory | Expectation decisions, verified regressions | `expectation_decisions`, `verified_regression_memory` keyed by sha256(SnapshotRef) | Until purge | Accessor-level membership check |
| SSE streams | Durable `assessment_events` replay | DB | Until purge | Members only (checked before stream) |
| Logs | Structlog lines (no source payloads) | stdout/host | Deployment-dependent | Operators |
| Webhook payloads | Raw delivery bodies | `artifacts` rows with `project_id NULL` | Until purge | **No API path**; jobs only |
| Ingest tokens | Per-project bearer for runtime ingest | `ingest_tokens` SHA-256 hash | Until revoked/purge | Hashed; plaintext never stored |
| Secret-like runtime payloads | Quarantined — recorded as audit event only | Not stored | — | Nobody |
| Idempotency cache | API response bodies | `idempotency_keys` per user | Until purge | Owning user |
| Audit trail | Hash-chained action metadata | `audit_events` (append-only, DB-trigger enforced) | **Retained after purge by design** | Org owners only |
| Jobs | Payload incl. project binding | `jobs` | Until purge | Members via `GET /jobs/{id}` (trace stripped) |

**Deletion workflow (implemented):** `backend/backend/privacy.py::purge_project(engine, project_id)`
deletes all rows above in FK-safe order inside one RLS-scoped transaction, then
(post-commit) removes bare clones and refcount-zero artifact objects. Verified
by `test_purge_project_deletes_every_surface`.

**Not yet automated (honest gaps):**

- No TTL/retention scheduler — deletion is operator-invoked, not self-serve or timed.
- Database backups (platform-managed, e.g. Railway/Postgres dumps) retain
  deleted data until rotated out; purge only affects the live DB. Record backup
  retention windows per deployment.
- Browser responses carry only API data for the signed-in tenant (same-origin
  proxy forwards cookies; backend enforces membership per request).
- `audit_events` are never deleted (append-only by design, DB trigger enforced).

---

## 3. Verified controls matrix

| Control | Mechanism | Test evidence |
|---|---|---|
| Tenant read isolation (all surfaces) | `require_project` org-membership → 404 for non-members, on projects, repos, scopes, assessments (+report/runs/events/SSE/RoE), findings (+patches), approvals, artifacts, jobs, incidents, ingest tokens, snapshots + expectations/regressions/symbols, audits | `test_tenant_isolation_adversarial.py::test_outsider_cannot_read_any_project_surface` (28 paths) |
| Tenant write isolation | Same check with `member`/`owner` role floors on every mutation | `test_outsider_cannot_mutate_any_project_surface` |
| SSE stream isolation | `_assessment_access` before durable-event replay | `test_outsider_gets_no_sse_stream` |
| Artifact access | `project_id` must match caller's org; NULL-project artifacts unreachable | `test_artifact_id_guess_grants_nothing`, `test_projectless_artifacts_are_unreadable_by_anyone` |
| Job lookup | Project resolved from payload/assessment; `last_error.trace` stripped | `test_job_lookup_never_leaks_trace_even_to_owner` |
| No ID-guessing privilege | knowing project/repo/scope/assessment/finding/artifact/job/snapshot IDs grants nothing without membership | entire file |
| Forged claims | foreign `repo_id` in scope → SCOPE_DENIED; repo connect requires recorded App access; ingest bearer bound to minting project; context pack requires exact snapshot match | `test_scope_cannot_borrow_foreign_repo`, `test_cannot_connect_repo_without_recorded_access`, `test_ingest_token_is_bound_to_its_project`, `test_context_pack_requires_exact_matching_snapshot` |
| Role floor inside a tenant | viewer reads, never mutates; owner-only gates (approve, ingest tokens, audit) | `test_viewer_role_boundary` |
| Storage-accessor tenancy | `SnapshotRef.project_id` must equal repo's owning project on every read/write; memory decisions require member/owner | `test_payload_store_rejects_forged_ref`, `test_memory_store_decision_requires_membership` |
| Row-level security | FORCE RLS on `index_payloads`/`index_snapshots`; rows exist only under `set_config('ari.project_id', …)` | `test_rls_blocks_reads_without_tenant_context`, `test_store_layer_sets_tenant_context_itself` |
| Deletion | `purge_project` full-project wipe incl. files | `test_purge_project_deletes_every_surface` |
| Session auth | SHA-256-hashed session cookie + `X-CSRF-Token` on mutations | `test_api_core.py::test_csrf_required_for_state_changes` |
| Webhook integrity | size bound → HMAC verify → dedupe → unreadable payload artifact | `webhooks.py` + artifact test above |
| Ingest auth | SHA-256 `hkt_ing_` tokens, revocable, rate-limited, secret-quarantine | `test_runtime_ingest.py` |
| Sandbox | Vercel microVM `deny_all`/custom netpol (prod); Docker `--network none`/internal-target-only net gated on authorized scope, cap-drop, read-only, no mounts, digest-pinned, uid 65534 | `security-agents/tests/test_sandbox*.py`; local-process driver dev/test-only |
| Audit | append-only hash chain, verified on read, owner-only | `test_api_core.py::test_audit_log_is_hash_chained_and_append_only` |
| Redaction | `redact()` on all non-assistant messages + tool results before provider, and on stored transcripts/artifacts | `llm.py` + `test_llm_gateway.py` |

**Failing-then-passing story:** the adversarial file is the regression gate —
any future route that forgets `_access`/`require_project`, any accessor that
trusts caller-supplied IDs, or any deletion that leaves a surface readable
fails immediately.

---

## 4. Application authorization model

- `require_project(conn, user, project_id, min_role)` resolves
  project → org → membership; outsiders get 404 (`not_found`), members below
  the role floor get 403. `_ROLE_RANK`: viewer < member < owner.
- `require_user` = valid `hackatl_session` cookie; CSRF compare_digest on all
  non-GET; sessions stored as SHA-256 hashes with TTL.
- Owner-only: project/repo mutations, scope approve/revoke, ingest tokens,
  incidents create/actions, audit log, control grants, emergency stop.
- Member+: assessments, finding reads, intelligence context.
- Rate limiter + idempotency with `pg_advisory_xact_lock` on mutating routes.

## 5. GitHub installation tokens (verified)

`backend/github.py::GitHubApp.installation_token`:

- **Short-lived:** GitHub-issued 1-hour tokens; in-memory cache TTL 3000s,
  refreshed when <120s margin. App JWT ~9 min.
- **Least-privilege:** read tokens request `{contents: read, metadata: read}`;
  write tokens `{contents: write, pull_requests: write, metadata: read}` and
  are pinned to exactly one repository.
- **Never persisted or logged:** `_tokens` is an in-process dict keyed
  `(installation_id, write, repository)` — no disk, no DB, no log statements.
  Tokens reach `git fetch` via `GIT_CONFIG_KEY_n`/`http.extraHeader` env vars,
  never argv or the repo's config.

## 6. Row-level security — decision record

**Decision: implemented** on `index_payloads` + `index_snapshots` (the tables
holding customer source bytes and their index). Migration `0016` enables +
forces RLS; policy `FOR ALL USING/WITH CHECK project_id =
nullif(current_setting('ari.project_id', true), '')`. All accessors
(`_validate_ref`, `find_snapshot`, `PostgresMemoryStore._validate`,
`purge_project`) call `set_config('ari.project_id', pid, true)` first inside
their transaction — transaction-local, reverts at commit, cannot leak across
pooled connections.

Why only these tables: they are the only store of raw source content, and both
are touched by exactly two modules, so the GUC contract is airtight. Extending
RLS fleet-wide is *proposed*, not implemented — the app-layer checks are now
test-covered on every route; widening RLS requires per-request tenant
resolution before first query (routes that resolve tenancy *from* the row
can't pre-set a GUC) and is deferred to a dedicated change.

Postgres superusers bypass RLS — production must not run the app as a
superuser (verify role on deploy). Verification uses a non-superuser probe
role in tests.

## 7. External AI provider (Anthropic)

- All model calls go through `LLMGateway` (`backend/llm.py`): budgets,
  tool allowlists, schema-validated outputs.
- **Repo code context IS sent to Anthropic** — it is the product. Customers
  must be told this plainly.
- `redact()` scrubs the system prompt, all non-assistant messages, and tool
  results (patterns: `sk-ant-*`, `gh[pousr]_*`/`github_pat_*`, `AKIA*`,
  `xox*`, PEM private keys, `Bearer` tokens; credential-keyed dict fields).
  Assistant-role turns are re-sent unredacted because provider thinking-block
  signatures bind to exact bytes — inbound redaction on tool results mitigates
  but does not eliminate residual risk.
- Stored transcripts ARE redacted (`put_json` → `redact()`).
- **Data processing/retention: no zero-retention claim.** Anthropic's standard
  API terms apply (30-day abuse-monitoring retention) unless the operator
  holds a separate agreement — configure per deployment and disclose to the
  customer. Do not promise otherwise.

## 8. Enterprise isolation — *future option, documented, not implemented*

Proposed capability for enterprise contracts: a dedicated stack (separate
Postgres, separate `ARTIFACT_STORE_URI` bucket, separate worker fleet, separate
Vercel Sandbox team, per-tenant Anthropic key) selected at project creation.

**Not available today:** everything above runs shared multi-tenant infra
protected by app-layer + RLS isolation. Sales/docs must not claim dedicated
AWS, single-tenant, or customer-hosted deployment exists. Implementation
ticket should cover: per-project infra routing table, secret namespace
scoping, separate backup policy, and an isolation attestation test.

## 9. Encryption, keys, operator access, incident response

- **In transit:** TLS at the edge (Railway/Vercel terminates TLS); internal
  Postgres connections per deployment (`sslmode` — verify on deploy).
- **At rest:** Railway volume encryption at the platform level for bare clones
  and the artifact store; Postgres storage encrypted by the provider. Record
  the platform's at-rest guarantee per deployment — do not claim envelope
  encryption/AES-256 specifics without evidence.
- **Keys/secrets:** env-only (`settings.py` SecretStr fields); never in repo;
  `.env.example` placeholders only. GitHub App key on disk is deployment-ops.
- **Operator access:** prod DB/console access is the audit boundary — session
  cookie auth for users; operator actions land in `audit_events` (hash chain,
  verified on read) where they touch product surfaces.
- **Incident response:** `docs/security/NIST_INCIDENT_HANDLING.md`; hash chain
  gives tamper evidence for tenant-facing actions.
