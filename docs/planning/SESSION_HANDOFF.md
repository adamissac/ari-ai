# Session handoff log

Append-only. Newest entry at the top. Every development session (human or agent)
adds an entry before ending.

## Template

```
### YYYY-MM-DD — <who / agent> — <task IDs>
- Did:
- State of the code (what exists now, verified how):
- Commands run and results:
- Decisions made (ADR links):
- Assumptions / open questions (RQ links):
- Next steps:
- Warnings for the next session:
```

---

### 2026-10-24 — Devin (agent, Adam) — code-intelligence pipeline audit
- Did: on `feat/adam/intel-pipeline-audit`, audited ingest→extract→store→retrieve→memory for pilot readiness. Reproduced the PR #441 redaction/parser regression on main (38/582 tracked .py unparseable post-redact + 2 line-count shifts); verified the fix (0 broken, 0 line shifts, 0 leaked literal secrets across the same corpus). Indexed payments-lite, `backend/` prefix, and the whole repo; ran a labeled-question retrieval eval; benchmarked latency/memory. Found a silent coverage gap — `@app.get(FIXTURE_ROUTE)`-style non-literal route paths were dropped with no IndexIssue — and fixed it so they are flagged. Carries `7a5b329f` verbatim, so merging this branch lands PR #441's fix.
- State of the code (verified how): `code-intelligence/tests` 57 passed 1 skipped; `backend/tests/test_intel_store.py test_intelligence_memory_api.py test_intelligence_ingestion_profile.py test_payload_store_intel_integration.py` 9 passed on real Postgres; new retrieval eval + route-diagnostic tests pass; benchmark harness executed on payments-lite.
- Commands run and results: `PYTHONPATH=code-intelligence:shared .venv/bin/python -m pytest code-intelligence/tests` (57 passed, 1 skipped); backend intel subset (9 passed); index runs 0.16s/8 files, 4.11s/127 files, 92.4s/1,798 files.
- Report: `docs/research/intel-pipeline-audit/README.md`; measured numbers: `code-intelligence/evidence/m2-index-retrieval-audit.json`; benchmark: `code-intelligence/evidence/index_benchmark.py`.
- Assumptions/open questions: secondary-evidence Recall@K degrades at scale (82% on payments-lite, 63% on ari-ai) — packs do not mark absent expected evidence; mid-line bare-secret expressions (`f(password=x, user=y)`) are a documented redaction residual; JS/TS extraction is unimplemented and unclaimed.
- Next steps: merge after review; consider BM25 tie-breaking toward implementation symbols if reviewers need secondary evidence.
- Warnings: none.


### 2026-10-24 — security/privacy lead (Devin session 94914ecc)
- Did: Audited private-code data flows end-to-end and wrote `docs/security/TENANT_DATA_PROTECTION.md`; added `backend/tests/test_tenant_isolation_adversarial.py` (17 tests: 28-path read denial, write denial, SSE, artifacts incl. NULL-project, jobs trace-strip, forged scope/repo/context-pack claims, ingest-token binding, viewer floor, forged-ref payload/memory stores, RLS probe-role verify, store GUC smoke, full purge); implemented FORCE RLS on index_payloads/index_snapshots (migration 0016 + `set_config('ari.project_id')` in `_validate_ref`, `find_snapshot`, `PostgresMemoryStore._validate`, purge); implemented `backend/privacy.py::purge_project` (FK-safe full tenant delete + refcount-aware artifact objects + bare-clone removal; audit_events retained by design).
- State of the code: all 334 backend tests pass incl. 17 new adversarial tests; ruff clean on touched files; no isolation hole found at app layer (require_project uniform).
- Decisions: RLS scoped to the two source-content tables only (documented in doc §6); purge is operator-invoked, no TTL scheduler (documented gap).
- Open: extend RLS fleet-wide needs per-request tenant GUC resolution — deferred; backups retention is deployment-level (documented).
- Warnings: `test_repository_has_a_single_migration_head` expects head 0016 — next migration must update it to 0017.


