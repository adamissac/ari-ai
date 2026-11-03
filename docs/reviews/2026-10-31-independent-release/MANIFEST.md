# Evidence manifest

Captured 2026-10-31. Raw GitHub records and local logs accompany this file.
Local machine: macOS arm64, Python 3.12, PostgreSQL via pgserver, fake providers.
No customer or production target was exercised. Tests used an isolated checkout under
/private/tmp/ari-release-audit/repo and an existing workspace venv. Set:

```
PYTHONPATH=backend:shared:standards:monitoring:security-agents:code-intelligence:code-review:specialists
```

Run `python -m pytest -q` followed by the paths below on the corresponding SHA.

- `9437e217d65aa1be22fa7b4f54f723200cd428c8`: `backend/tests/test_tenant_isolation_adversarial.py backend/tests/test_project_get_authz.py backend/tests/test_jobs_queue.py backend/tests/test_operator_budget_cap.py backend/tests/test_auto_delivery.py backend/tests/test_parallel_migrations.py tests/security` → 103 passed, exit 0; `tests-main.log`.
- `7e5c7351598255e5394df45b5ca4a5a1a00e36a0`: `backend/tests/test_review_pipeline_reliability.py backend/tests/test_pr_review_effect_ownership.py` → 37 passed, exit 0; `tests-693.log`.
- `72753087abef39a84103fe9fbcf43248430a7ebb`: `backend/tests/test_disconnect_write_token_ordering.py backend/tests/test_security_audit_disconnect_writes.py backend/tests/test_redaction_literal_forms.py` → 33 passed, exit 0; `tests-694.log`.
- `9cbacc3ed5a787992e8e4de95021faa2ba31abcd`: `backend/tests/test_release_signoff_binding.py backend/tests/test_staging_pilot.py backend/tests/test_preflight.py backend/tests/test_parallel_migrations.py` → 46 passed, exit 0; `tests-695.log`.
- `e0622b8d91dfb332cea5587147eda3418f3cd810`: `backend/tests/test_delivery_authority_view.py` → 6 passed, exit 0; `tests-696.log`.
- `56204e4aa073540125489ac7e54a080ec6abea3d`: `tests/ops/test_uptime_watch.py` → 8 passed, exit 0; `tests-723.log`.
- `79067534d044c097140b5aa60469caeb1629cb33`: `backend/tests/test_assessment_restart.py backend/tests/test_e2e_host.py` → 26 passed, exit 0; `tests-725.log`.

Frontend #696: `vitest run tests/unit/first-customer-ux.test.tsx tests/unit/onboarding-stepper.test.tsx`
→ 17 passed, exit 0; frontend-696.log. Existing node_modules were symlinked locally;
this is a focused test, not an independently installed full frontend build.

Initial sandboxed #693 test startup was blocked by pgserver cache permissions (exit 4);
the authorized local-database rerun passed. Wrong local-clone tracking ref was corrected
to explicitly fetched canonical/main before the reported integration/test runs.
No failed setup is counted as a product failure or a pass.

Main-checks JSON was read at the exact main SHA. PR JSON records preserve full head,
merge status, files and checks. `composition.json` preserves merge-tree exits/conflicts;
merge-693/694 logs preserve the sequential attempt. Redaction JSON uses only synthetic
canaries and actual unified-diff headers. Certification JSON uses mocked GitHub responses.
Historical large e2e log is retained in /private/tmp/ari-release-audit; the relevant
landing failure excerpt is committed here. Live GitHub source is run 40975638724.

## SHA-256 evidence hashes

- `696-e2e-excerpt.log`: `fb30debd77ff9c52168c2e3987b8b95b563f139b6756625e07600e15265293ac`
- `composition.json`: `4c623a8a77062ef7180bd29246054dba6ea06403ddeafab933b3a75f1b36d60e`
- `conflicts-694.txt`: `76c6cbe130f1ec726602318a38e84686d3b49f6e1016aa3a0235b3ada994a6ca`
- `frontend-696.log`: `8357d1e2d60a82641bb73b7616951e2c28509ee7bfca0fed810182eedede6cdf`
- `main-certification-probe.json`: `21b7127ea3ea7b15761e1fab61feec738996ccdfa4c9b465ac5b8f1570022178`
- `main-checks.json`: `d5f54f423a7fc11e873559b94d76a56a6ee90826236aada08123ae55774ff755`
- `main.json`: `d2fa3326b54f6f8e9f60c62925ff9affb5d1f67f67169de481dc39726a6e8ee6`
- `merge-693.log`: `96bb6a194a796153cbd0c640642866371219451832063763d544b942a8d97c4e`
- `merge-694.log`: `dd03aef02c9decf3db6d00229018d80433fa446af22e250888731aa09463dab9`
- `merged.json`: `308f6c8c7c1970ff4329be205c681f3ec9a090a5a7a55555fa3ec3c7a2b8a4cb`
- `open.json`: `24eac7a33c0fe08c5d40ae5f2b3b1e1aaaef62c1b8f55afb96bd2094295561ed`
- `pr-693.json`: `29085455f0dbfd8c7bc3ae9939d6c23b7a50958b5797da610b74919bde0dfa85`
- `pr-694.json`: `95bc0a5bfe0a07858c7e6521048e4c7d78c93b39a802fd9b49244285096aedab`
- `pr-695.json`: `95f6cd99a658b0e24b0d90de6d193e2e2457c48dab751f7dc5b857ff36151497`
- `pr-696.json`: `230252a4c0bf3d795af63d4e3a78b57eb246142158a49b97833bf456400df832`
- `pr-723.json`: `10dcade4e8d492fd389e6d4ffb40e702000564b0bc3543913450ae3bb4f7869d`
- `pr-725.json`: `c3c757ac99f03cdee2d96003e98f5a73bb5b9b4899797c0634ef0fb8dbc3f106`
- `pr693-final.json`: `816bcf9b2c687bd4716a6447efacb5c8089759515c87e8588b373ddf2db73188`
- `pr694-final.json`: `33ac1ab280efa80f0b10931c4db84ca8ce401b05d7a804b64ae1e8275b9bab75`
- `protection.json`: `75c603659be44328a1f22ab62601fcc15ab614458ee7c15edcc683798d9877a9`
- `redaction-probe.json`: `6f08338570cf4f42434df5dd9c31ab1d7432d5bea40240bc2ebe81f3a943d1a4`
- `tests-693.log`: `e4d9a8944a75ba75e90930a17af9218ded96a0176c9206d3c2bd44cb659e760a`
- `tests-694.log`: `11bce3a6afb5d911bae5b153fa8db9fef4e89dbe8f305df339899a5edc18cd54`
- `tests-695.log`: `8331c0d38d51ecc2534101bb899339a3f2dc9936a14a5ab64f80aeebb5aca9ba`
- `tests-696.log`: `e6e7b4a1138cb3b0dae07c24e036094e8fb52f96fec4c40f2ed4fdd347aa9c5c`
- `tests-723.log`: `71288863ec9567395a647dd0c8fbf0e2048bee72283202612ad6f90a7a526ef3`
- `tests-725.log`: `e70601456b6fb2687ee32cb0e394601d6604cbdadf89a825208584be9539440d`
- `tests-main.log`: `5bf7ad029c6a5167f87b4c93532e94df07cd7682a842e37b091dfb0d6aa52e2e`

## Reproduction and final refresh

Run `python3 docs/reviews/2026-10-31-independent-release/reproduce_probes.py` from the repository; fetch the pinned #694 object if absent. Exit 0 reproduces three main redaction failures, their #694 controls, and two false-green certification cases. Final explicit PR refresh found main and all six heads unchanged and all six PRs OPEN/BEHIND.

- `reproduce_probes.py`: `2dec6f04d56dba3009373778e823a581c2c4e2c8ffe0c15e4bad96ad16fc9a91`
- `open-final.json`: `902f30aaa162bad9491570399cbc097ed7cb5cb8f3cf09ca98a57e907aeb2a0e`
- `issues-final.json`: `218374725bb7dc07833a261d9b1e6b0fc092f84018e8289b7c33a981d7626d58`
- `pins-final.json`: `80d7d0e8cfd9e5ecd81aed95a4f66011a6e7a9ac99c22ed9d90289f8d8fcd354`
- `reproduced-probes.log`: `fcfa88eb4eb7980402720a3db938b923a7e0452050e9a8d6f9b337123ca860c6`
