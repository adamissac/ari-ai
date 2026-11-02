# notes-firebase-lite

Owned JavaScript fixture for the security agents ([ADR-0023](../../docs/decisions/0023-js-ts-security-agent-testing.md)):
a Vercel function backed by firebase-admin, plus Firestore rules. It runs only against the
Firebase emulators inside the sandbox; `demo-notes-lite` is a `demo-` project id, so the
SDKs never contact Google.

Planted defects, on purpose:

- `GET /api/notes/{id}` returns any note to any signed-in user (BOLA).
- `profiles/{uid}` rules allow any signed-in user to read and write any profile.
