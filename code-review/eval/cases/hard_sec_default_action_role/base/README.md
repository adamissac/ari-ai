# authz

Roles, least to most privileged: member, admin, owner.

## Rules

- Every action names the lowest role that may perform it.
- An action that is not listed, or a role that is not listed, is denied.
