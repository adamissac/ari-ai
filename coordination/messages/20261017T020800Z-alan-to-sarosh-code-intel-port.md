# MSG: the exact code-intelligence surface the seven agents consume
- ID: `20261017T020800Z-alan-to-sarosh-code-intel-port`
- From: alan
- To: sarosh
- Kind: `contract-proposal`
- Timestamp (UTC): 2026-10-17T02:08:00Z
- Branch / commit / PR or issue link: `feat/alan/seven-agent-runtime` @ `b0ae682`
- Related subsystem(s): `code-intelligence/`, `security-agents/`

## Summary (facts, not assumptions)

The security agents are built against a narrow consumer port, not against your
internals, so your implementation can replace mine without touching an agent.
The port is `security_agents.intel.CodeIntel`; until `code_intelligence.api`
exists I ship `LocalIntel`, a real (not mocked) Python-`ast` index over a pinned
snapshot. It reports its own limits through `provenance()`, so nothing presents
it as the full index:

```json
{"adapter": "security_agents.intel.LocalIntel",
 "status": "LOCAL ADAPTER pending code_intelligence.api (INTEL-007)",
 "parser": "python-ast", "languages": "python",
 "call_resolution": "name-based, confidence=likely",
 "expectations_origin": "injected (labels fixture)"}
```

## Interface requested/proposed (field-level types)

```python
class CodeIntel(Protocol):
    @property
    def snapshot(self) -> SnapshotHandle: ...        # snapshot_id, repo_id, commit_sha, root, pinned_by
    def provenance(self) -> dict[str, str]: ...
    def read_span(self, path: str, start_line: int, end_line: int) -> Span: ...
    def search(self, pattern: str, *, max_results: int = 20) -> list[dict]: ...   # regex; path/line/text
    def symbols(self) -> list[SymbolInfo]: ...
    def neighbors(self, qualified_name: str) -> dict[str, list[str]]: ...
    def entry_points(self) -> list[shared.intelligence…EntryPoint-shaped]: ...
    def expectations(self, subject_ref: str | None = None) -> list[BehavioralExpectation]: ...
```

What each agent actually depends on, so you know what matters:

| Consumer | Needs | Why |
|---|---|---|
| Scout | `entry_points()` with `auth_dependencies`, `neighbors()` callees per handler, `expectations()` | The whole hypothesis rests on comparing a handler with its siblings: on `payments-lite`, `get_payment`'s callees lack `require_owner` while `get_customer`, `get_refund` and `create_refund` have it. That single difference is the signal. |
| Scout/Trace/Diagnose/Fortify | `read_span()` returning the exact lines **with line numbers** | Every citation is validated against the snapshot; a hypothesis citing a line range that does not exist is dropped, so wrong spans cost recall. |
| Trace | `neighbors()` far enough to reach data access, plus `expectations().data_sensitivity` | Severity is computed from factors including data sensitivity. |
| Diagnose | `neighbors()` callers, `search()` | To locate the shared function that should enforce the guarantee, not the symptom. |
| Probe/Verify | `expectations()` only | They work against the running target, not the index. |

Two field-level asks:

1. **`SymbolInfo.calls` must distinguish resolution quality.** My adapter labels
   an ambiguous name as `"public (ambiguous: 2 candidates)"` and an unknown one
   as `"name (unresolved)"`. docs/12 has `CallEdge.resolution: exact|likely|unresolved` —
   please surface that through `neighbors()` (e.g. `callees: [{name, resolution}]`),
   because Scout's sibling comparison is only sound when a missing call is
   genuinely missing rather than unresolved. If you prefer the flat list, keep the
   suffix convention above and I will parse it, but typed is better.

2. **`EntryPoint.auth_dependencies` is not enough on its own.** On the canonical
   fixture, authentication is a FastAPI `Depends`, but the ownership check is a
   plain call *inside* the handler body (`require_owner(...)`). So a route can
   have identical `auth_dependencies` to its siblings and still be the planted
   finding. Please keep in-body calls visible via the call graph (my adapter
   does), or add something like
   `EntryPoint.guard_calls: list[str]` — the names called before the handler
   returns a resource.

## Expectations: who produces them

Today `LocalIntel` takes expectations injected from
`examples/payments-lite/labels.yaml` via `security_agents.intel.load_expectations`,
which reads **only** the `expectations:` section and marks every record
`origin="fixture"`. The answer-key sections (`planted_findings`, `negatives`)
are reachable only through `answer_key()`, which is for evaluation scripts — no
agent can see them. When you derive expectations from the target (docstrings,
tests, the `require_owner` convention, README), `LocalIntel` goes away and I use
yours; the two expectations I need for the demo are `exp_owner_only` and
`exp_refund_bound`, with `data_sensitivity: financial`.

Note for both of us: `shared.ids.ExpectationId` is `^exp_[0-9A-Za-z]{8,64}$`,
which **rejects** `exp_owner_only` (underscores). I have asked Srihith to relax
it (`20261017T020600Z-alan-to-srihith-contracts-v0-ack.md`, delta 2). If he
declines, your derived ids need to be ULIDs and the fixture has to change — worth
knowing before you emit ids.

## Breaking change? migration/test impact

None yet. When you ship `code_intelligence.api:build_service()`, I write a thin
`CodeIntelAdapter` satisfying the protocol above and delete `LocalIntel` from the
default path; my 325 tests then run against your index, which is the real
integration test for both of us. If your signatures differ, send them and I will
adapt rather than asking you to match mine.

## Action required by recipient

1. Confirm the port is implementable as written, or send your signatures.
2. Say whether `neighbors()` can carry call-resolution quality (ask 1) and
   in-body guard calls (ask 2).
3. Tell me when `index_snapshot` can produce `exp_owner_only` /
   `exp_refund_bound` for `examples/payments-lite/target`, so I can drop the
   labels fixture.

## Response-by milestone

Before M1 sign-off (index + expectations + context packs on the owned example).

## Evidence: command output, test status, logs or exact file paths

```
cd security-agents && .venv/bin/python -m pytest tests -q
325 passed, 3 skipped in 88.51s
```
- port + adapter: `security-agents/security_agents/intel/port.py`
- labels loader (interim): `security-agents/security_agents/intel/labels.py`
- the sibling-difference signal, as a test:
  `security-agents/tests/test_tool_registry.py::test_graph_neighbors_exposes_sibling_difference`
