# MSG: Context citation privacy fix #190

- From: sarosh
- To: sai, alan, srihith
- Timestamp: 2026-10-17T15:23:11.514060+00:00
- Branch: feat/sarosh/intelligence-maintenance
- Issue: https://github.com/adamissac/hackatl-agentic-security/issues/190

Reproduced with a fake bearer-shaped canary: chunk body was redacted but raw
human-decision reason leaked through EvidenceRef.note in structured provenance
and embedded citation JSON. Existing known-key validation rejects PAT-shaped
strings, but it is a cheap tripwire and does not replace output redaction.
The public expectation view had the same metadata issue; reproduced separately.

Fix copies/redacts free-form citation note/provenance at output boundaries, then
validates bounded metadata. SHA, source path/span/symbol, artifact pointers,
expectation IDs/statuses, stored decisions/history and immutable indexes remain
unchanged. Context packs and expectation views use the same helper. No shared
DTO, parser version or reindex/migration change.

Executed so far: focused privacy10 passed; broader producer/shared/PostgreSQL
107 passed/1 opt-in live inference skip; strict producer mypy12 modules, Ruff
and format passed. Hosted reviewer/security/monitoring consumer checks11 passed.
No real credential, provider call or third-party target used. Active frontend
work remains untouched. Please flag any downstream display assumption about
free-form notes; authenticated history still exposes original reasons.
