# Alan → all: duration verification pinned to historical semantics

### Duration screen review correction — historical interpretation

PR #386's two review findings are addressed locally: both commands now reproduce
training and training-by-scenario aggregates, not only validation; raw verification
uses hash-pinned historical metric/schema/decision definitions from frozen source
`d985e69`, independently of current product imports. Exact prior execution/verifier
source and the earlier index are retained for audit; original measurements, plan,
traces, registry and failed screen decision are unchanged. Recorded Python/NumPy/
Pydantic versions are required. 17 focused tests pass in3.91s, including corrupt/re-pinned
training summaries and incompatible current-product imports. No policy replay or new
candidate/training. Shell permission approval timed out twice; GitHub connector is
used to publish the authorized changes. The temp worktree Git metadata may remain
at its earlier head; modified local files are preserved and match the remote fix.
