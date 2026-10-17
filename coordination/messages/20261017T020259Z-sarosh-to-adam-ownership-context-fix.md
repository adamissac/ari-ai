# Route ownership expectations corrected after cross-pillar review

- From: sarosh
- To: adam, alan, sai, srihith
- Timestamp (UTC): 2026-10-17T02:02:59Z
- Branch / PR: `feat/sarosh/code-intelligence`, #6
- In-Reply-To: Adam's cross-pillar review on PR #6
- Confirmed gap: module-level ownership intent was not attached to the vulnerable payment-read route; `get_store` was incorrectly listed as authentication.
- Implemented: resource-matched module ownership rules attach directly to EntryPoint IDs. Same-app/router resource-by-id GET siblings with a majority of statically identified ownership checks produce a medium-confidence **possible inconsistency** on an outlier. Sources cite sibling call sites at the same SHA. Ownership helpers require an identity equality/inequality comparison and explicit 401/403/404 rejection; nested functions are not treated as checks executed by the enclosing function.
- Authentication: `get_store` remains a call/dependency graph edge but is excluded from `auth_dependencies`. `current_customer` remains; in-body `require_owner` checks are recorded on the protected handlers. These are static signals, never proof of runtime enforcement.
- Retrieval/API: route-subject expectations are available through route ID, handler ID/name and path aliases. They are included in route/expectation-focused ContextPacks and diff invalidation. Module rules remain ambiguous (0.55); sibling inconsistency remains ambiguous (0.6), not a vulnerability verdict.
- Freshness: bumped INDEX_VERSION to `python-ast-ts/0.2.0`; re-index to obtain the improved intent facts. Old 0.1.0 payloads remain explicitly versioned and are never silently returned by current-version SHA lookup.
- Executed test: `test_vulnerable_route_gets_cited_ownership_convention_and_fix_invalidates_it` indexes the actual owned target, proves the missing route gets the rule and two sibling citations, inserts `require_owner` in a second commit and proves the warning disappears at head. No target application/test code is executed by this test. Intelligence suite: 19 passed, 1 live opt-in skip before version-only regeneration; final combined results follow in PR.
- Consumers: re-index using current index version and retain the complete returned SnapshotRef. No parallel indexer or label-file trust is needed.
