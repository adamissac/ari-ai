# UI provenance follow-ups: #262, #273, #278

- From: Sarosh
- To: Sai, Srihith, Adam, Alan (cc: all)
- Branch: `feat/sarosh/demo-provenance-labels`
- PR: https://github.com/adamissac/ari-ai/pull/282

Taking the remaining frontend provenance fixes requested in the issue queue. #278 now distinguishes real GitHub metadata from illustrative analysis. #273 UI describes synthetic counters, real routes/detection, Claude or scripted planning, recommendations only and no service attack traffic; pending text no longer guarantees Claude. #262 labels saved evidence separately from sample-account data, adds the missing unpatched-test/red-to-green caveat and updates the runbook for access-code setup and repository-root commands.

No backend/shared-contract changes. Srihith's baseline-history isolation, provider usage accounting and durable rate-limit concerns remain open on #273. No provider run or deployment-setting changes. The raw historical report remains gitignored and retained by Alan; this pass uses the curated summary and documented limitation.

Initial verification: lint, typecheck, production build, 246 unit tests and four demo browser tests passed; 385 internal links checked with zero problems. Desktop/mobile visual inspection caught a long recorded assessment-ID overflow, now addressed with wrapping and a phone assertion. Integrating current main (including #279 and #281) and rerunning final checks next. The changed files do not overlap those PRs.
