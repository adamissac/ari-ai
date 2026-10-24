# Verification and reproduction

Analysis source0074562408b0c302e0c00f8a4226862bacdbaa7e was committed/pushed before
calculation. The60-second/256MiB stdlib-only tool read120 existing workload records,
verified the original indexed artifacts and wrote new bounds outside the study.
No environment, policy, model or holdout was loaded or executed.

Read-only command used once for the retained analysis:
`python scripts/research/resource_bounds.py /private/tmp/ari-resource-bounds-001`.
New outputs refuse overwrite. No repeated original feasibility execution occurred.
Original source/protocol and600 episode receipts remain byte-identical.

Local checks executed for this assessment:

- 6 mathematical/provenance tests passed (1.05s), including every archived bound
 recomputed from recorded jobs, source-object hash and all original artifact hashes.
- 52 resource/preparation/study regression tests passed (2.35s);91 shared contract
 tests passed (0.96s).
- Strict mypy: no issues in the analytical source. Scoped Ruff and formatting passed.
- Markdown links:584 files, zero problems. Git whitespace check passed.

Scoped CI uses only pytest/Ruff for these read-only mathematical/provenance checks;
it never launches the archived study or trains a policy. Full product/RL pipelines
are unchanged. No deployment/customer-effectiveness or pilot-readiness test is
claimed from this tooling.
