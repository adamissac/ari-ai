# Contributors: AI authors → human Co-authored-by

**From:** Adam  
**To:** all  
**PR:** https://github.com/adamissac/ari-ai/pull/272

GitHub Contributors still lists `cursoragent`, `claude`, `cursor[bot]`, and `myWork-flg` (Alan’s fam.mozhoor commits). Mailmap cannot fix that graph.

#272 updates `scripts/rewrite_ai_commit_authors.sh` so a planned rewrite:
1. Maps AI-authored commits to the **human Co-authored-by** (Alan’s `amozhoor7` trailers → Alan; else human committer; else Adam).
2. Strips Cursor/Claude/Devin trailers (they still create contributor rows).
3. Normalizes duplicate emails for the six of us.

Dry-run in a throwaway clone leaves **only** Adam / Srihith / Sai / Alan / Vihaan / Sarosh as authors.

**Force-push still held** per Srihith’s post-demo note on #267. When we flip it:

```bash
I_APPROVE_HISTORY_REWRITE=yes ./scripts/rewrite_ai_commit_authors.sh
git push --force-with-lease origin main
```

Everyone must re-clone or hard-reset feature branches afterward.
