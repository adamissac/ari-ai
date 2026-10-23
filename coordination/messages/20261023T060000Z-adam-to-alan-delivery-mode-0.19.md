# Adam to Alan: shared 0.19.0 delivery_mode (ADR-0021)

Additive shared change for review: `ProjectSettings.delivery_mode` (`review` default | `auto`) and server-set `auto_delivery_enabled_by`. Default keeps today's behaviour. Auto mode pre-approves remediation in the enabling owner's name and pushes only Verify-accepted patches (new job `deliver_verified_patch`). Generated contracts included. Note: open PR #393 also bumps the schema version; whichever merges second renumbers.
