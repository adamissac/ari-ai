# pilot-rehearsal-target

Private staging target for the ARI limited pilot rehearsal — a two-tenant
Python ledger API (`ledgerlite/`) with one deliberately planted defect.

## Planted defect

`GET /entries/{entry_id}` fetches the row and returns it without checking the
caller's `account_id` — a missing object-level authorization check (CWE-639 /
BOLA). Every other route enforces ownership correctly, so a correct reviewer
flags exactly this route and nothing else.

## Layout

- `ledgerlite/app.py` — FastAPI app + sqlite store + the planted defect
- `build_recipe.json` — ARI build recipe (identities, resources, routes)

## Run

```sh
uvicorn "ledgerlite.app:create_app" --factory --port 8000
# tokens are seeded per user (see ledgerlite/app.py + build_recipe.json)
# alice reads her own entry:      curl -H "Authorization: Bearer $ALICE_TOKEN" :8000/entries/ent_a1
# the defect — bob reads alice's: curl -H "Authorization: Bearer $BOB_TOKEN"   :8000/entries/ent_a1
```
