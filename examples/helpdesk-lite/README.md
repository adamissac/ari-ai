# helpdesk-lite — harder owned evaluation fixture

A deliberately defective FastAPI support desk, built to separate models that the two small
fixtures (`payments-lite`, `inventory-lite`) cannot: its package is split across eleven
modules, each defect needs code from a second file to see, and every defect has a correct
lookalike beside it.

- `target/` — the app the platform indexes and builds. Four planted weaknesses, at class level:
  - an ownership rule with an exception the README does not allow (CWE-639);
  - one router mounted without the sign-in dependency its siblings have (CWE-306);
  - a search helper that places the search text in the SQL (CWE-89), next to a search that
    builds its SQL with an f-string but binds every value;
  - a file helper that rejects `..` but lets an absolute name replace the folder (CWE-22),
    next to a download that resolves and confines its path.
- `build_recipe.json` — operator-approved sandbox recipe (fixture identities, resources and
  routes a reviewed check template may name; not an answer key).
- `labels.yaml` — ground-truth answer key, kept outside `target/`. Its `expectations` restate
  the target README's rules for correct and defective areas alike.
- `label_checks/` — proves each planted defect exists, each lookalike is safe, and the recipe
  matches the app:

      uv venv --python 3.12 target/.venv
      uv pip install --python target/.venv/bin/python -e "target[dev]" pyyaml
      target/.venv/bin/python -m pytest -q label_checks

Never deploy this target. Synthetic data only.
