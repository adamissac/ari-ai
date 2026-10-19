---
from: devin (Adam lane)
date: 2026-10-19
summary: specialists corpus-2 + real-corpus training in flight on feat/adam/specialists-real-corpus
---

Retraining the seven specialists on a diversified synthetic corpus (corpus-2,
5-6 families/CWE, varied CauseClass and strategy labels) augmented with real
public corpora: DiverseVul (commit-bucket splits, vuln_other class for
out-of-space CWEs), NVD CVE descriptions (Trace), ATT&CK STIX descriptions
(Fortify). Cache is fetched via `specialists.data.fetch` and git-ignored;
dataset digests still pin exactly what each checkpoint trained on. Version
bumped to 1.1.0. Checkpoints/results land when the run finishes.
