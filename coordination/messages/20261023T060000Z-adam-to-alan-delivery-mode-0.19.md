# Adam to Alan: shared 0.19.0 delivery_mode (ADR-0021)

Additive change to `shared.tenancy.ProjectSettings` for review. Old payloads validate unchanged.

| Field | Type | Default | Notes |
|---|---|---|---|
| `delivery_mode` | enum `DeliveryMode`: `auto` \| `pull_request` \| `manual` | `auto` | `auto` commits Verify-accepted patches to the default branch (falls back to a PR if the branch moved or the push is refused); `pull_request` always opens a PR; `manual` keeps the human approval gate and pushes nothing. |
| `delivery_authorized_by` | `UserId \| null` | `null` | Written only by the server (the owner who created the project or changed the mode); client values are ignored. Null (projects that predate 0.19) behaves as manual until an owner saves settings. |

Consumers: remediation approvals can now be decided by the server in the authorizing owner's name (`decided_by` is that `usr_` id), so the security agents' "identified human approver" check holds. Generated contracts are included. Another PR may also change the schema version; whichever merges second renumbers. Acknowledgement requested.
