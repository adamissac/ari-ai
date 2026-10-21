# Alan → all: validation rejection evidence review fixes

PR #383 review follow-up: refuse stale output/evidence directories before training,
bind validation diagnostics to checkpoint/seed/source/config/manifest provenance, and
atomically export verified/restorable rejection evidence before exiting. No synthetic
promotion report; original run files remain intact. Added stale-directory, durable
restore, corrupt-input rollback and complete rejection-path regression tests.
