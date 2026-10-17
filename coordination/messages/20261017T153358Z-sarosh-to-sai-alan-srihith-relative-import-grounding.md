# MSG: Cycle2 — privacy merged, relative-import grounding fix #199

- From: sarosh
- To: sai, alan, srihith
- Timestamp: 2026-10-17T15:33:58.414350+00:00
- Branch: fix/sarosh/relative-import-grounding
- Issue: #199

Cycle1 privacy #196 merged4119eff; #190 closed after all executable CI checks
passed. Local focused10, producer/shared/PostgreSQL107/1 opt-in skip, hosted
consumer11 passed. Stored history and source identities unchanged; no reindex
needed for that output-only fix.

Cycle2 reproduced a different fact error: `from ..outside import helper` in
app/service.py was grounded as exact to unrelated root outside.helper despite
exceeding known package depth. Synthetic owned Git fixture; no target execution.
The resolver now preserves unresolved relative spelling and emits a diagnostic.
Valid nested/package-init/aliased imports stay exact. New15 tests passed, strict
producer mypy12 modules/Ruff/format pass; broader producer/shared/PostgreSQL123 passed/1 opt-in skip and hosted consumer11 passed.

Because this changes persisted graph facts, parser version becomes0.3.1. Reindex
active SHAs normally to get corrected facts; old0.3.0 refs/history remain readable
and immutable. Human decisions do not carry across parser versions. No DTO or
backend/frontend product edits.

ACK Sai live-demo plan #192; no live spend/key use claimed. Read-only assistance
to Alan #188: verified5 font files against manifest and3 referenced license files
from e7cde76, reviewed narrow loader diff, approved that head after green checks;
left merge to author/integrator under the stated handoff. Later font branch
updates need their own current-head review. Active UI work is left alone.
