# docs

A multi-tenant document list.

## Rules

- Every query is limited to the caller's tenant. A caller never sees another
  tenant's documents, with or without filters.
- `status` narrows the list to one status.
