# Alan → all: RL merges and reviewed continuation

Owner authorized merges. #375 merged64c38b7; #376 mergedce723f8 (all checks green,
267 RL tests). Four late #376 review findings are corrected in #378 before its merge:
shared source fingerprint per job, source SHA in derived summaries, complete consistent
gates and staged evidence finalization with I/O rollback.64 focused tests pass;
78 stored artifacts/all five indices verify. Original v9 weights/reports/statistics
remain unchanged; the enriched summary adds provenance only.

#378 also holds the candidate action-balanced demonstration sampler, saved failure
diagnostics and fresh two-arm/five-seed v10 preregistration. No v10 training/holdout
evaluation has run, no model is selected/promoted and the real v6 registry is unchanged.
Remaining action: final CI/review then merge #378. Future study needs about6h CPU.
