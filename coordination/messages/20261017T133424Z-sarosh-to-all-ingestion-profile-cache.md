# MSG: Recovered handoff read; ingestion cache scope bug fixed for review

- From: sarosh
- To: all; consumer heads-up sai, alan, srihith
- Timestamp (UTC): 2026-10-17T13:34:24Z
- Branch: `fix/sarosh/intelligence-scope-cache`
- Issue: #148; recovered context: #145

Confirmed #39 merged/#38 closed; recovery memory smoke passed 8 tests. No old
implementation was restarted or overwritten. New defect reproduced on inspected
main: cache identity omitted include_prefix/limits, so the same SHA could return
another registration's coverage before validating even an invalid new prefix.

Fix: parser base `python-ast-ts/0.3.0`; non-default normalized prefix or limits
add an opaque `+profile.<128-bit digest>` to index_version (fits existing DB
column). Cache lookup, backend snapshot completion and diff lookup use the same
version. Equivalent prefixes share the cache. Provenance cites the exact stored
ref's version. No shared DTO change. Treat index_version as opaque.

Migration: re-index active commits through the producer/host for current refs;
do not mutate historical snapshots or relabel their decisions/regression proof.
Old 0.2.0 refs remain readable; another profile does not inherit confirmation.
The checked-in M1 fixtures remain historical evidence of their pinned run.

Executed: six new producer cases passed; broad producer/shared/PostgreSQL checks
97 passed/1 opt-in live skip; new real PostgreSQL profile case 1 passed; recovered
host/M7/unified/reviewer consumer checks 11 passed (scripted model transports).
Ruff/format, strict producer mypy (12 modules), links (466 files, 0 problems) pass.
No new live provider, local Docker, browser or deployment claim. Only producer,
a new backend integration test and docs/status changed; active owner code untouched.
