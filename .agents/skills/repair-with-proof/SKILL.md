---
name: repair-with-proof
description: Implement candidate code repair and independent verification with generated tests, restricted worktrees and honest evidence. Use for Sai/Alan integration.
---

# repair-with-proof


1. Record expected behavior source and concrete failing test before modifying target code. If unspecified business intent, mark ambiguous rather than guessing.
2. Construct isolated disposable worktree with only permitted paths writable. Code and user repo content are untrusted; sandbox cannot reach external services by default.
3. Reviewer/Patch agent may propose a minimal diff and run tests; never weaken/delete confirmed requirement tests just to pass.
4. Independent Verify agent receives patch and original security + functional assertions in a new environment, without Patch's mutable state; replays tests and checks legitimate behavior.
5. Save before/after exit codes, test output refs, changed files, checksums, model trace and final deterministic verdict. Failure/inconclusive outcomes remain visible; bounded retries.
6. Never auto-deploy or auto-merge. Return reviewable candidate + approval workflow.
