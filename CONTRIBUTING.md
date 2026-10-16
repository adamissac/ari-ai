# Contributing

Thanks for helping build this. The project is in **Phase 0** (architecture only);
read [docs/23_TEAM_ONBOARDING.md](docs/23_TEAM_ONBOARDING.md) first.

## Workflow

1. **Pick a task** from [docs/planning/HACKATL_TASKS.md](docs/planning/HACKATL_TASKS.md)
   whose status is `READY`. Confirm with the team before taking an `UNASSIGNED`
   task; set its owner and status to `IN_PROGRESS`.
2. **Branch** from `main`: `<type>/<TASK-ID>-<short-slug>`
   (`feat/SEC-004-probe-sandbox-runner`). Types: `feat`, `fix`, `docs`, `refactor`,
   `test`, `chore`, `research`.
3. **Read the contracts** you will touch in `shared/` and
   [docs/12_DATA_MODELS_AND_CONTRACTS.md](docs/12_DATA_MODELS_AND_CONTRACTS.md).
4. **Build in small commits** using Conventional Commits:
   `type(scope): summary (TASK-ID)`. Scopes: `ui`, `api`, `intel`, `review`,
   `sec`, `rl`, `mon`, `shared`, `infra`, `docs`, `test`.
   Do not add `Co-Authored-By` or any tool-attribution lines.
5. **Test** — add tests for your change and run the subsystem's checks.
6. **Update docs** — subsystem README "What exists", task status, handoff entry,
   CHANGELOG `Unreleased`.
7. **Open a PR** using the template. Link the task ID. Keep PRs under ~500 changed
   lines of non-generated code where possible.

## Review expectations

- At least one approving review; two for anything touching
  `shared/`, authorization, sandboxing, or agent tool permissions.
- Reviewers check: correctness, contract compatibility, tests, security boundaries,
  documentation, and that no claim in docs/UI exceeds what the code does.
- Authors respond to every comment (fix, or explain why not).
- See [docs/24_DEVELOPMENT_STANDARDS.md](docs/24_DEVELOPMENT_STANDARDS.md) for the full review checklist.

## Contract changes

Changes to `shared/` or `/api/v1` are **contract changes**: label `contract-change`,
describe compatibility impact and migration, regenerate derived types in the same
PR, and get review from the contract owner. Prefer additive changes.

## Avoiding merge conflicts

- Stay inside the directory your task owns.
- Generated files (`shared/generated/**`) are regenerated, never hand-edited;
  resolve conflicts by regenerating.
- Rebase on `main` daily while a branch is open.
- Coordinate edits to hot files (`shared/`, `docs/planning/HACKATL_TASKS.md`) in
  the team channel; keep task-board edits to your own rows.

## Security-sensitive contributions

Anything that executes code, sends network traffic, or performs state changes must
go through the authorization and sandbox layers described in
[docs/15_SECURITY_BOUNDARIES.md](docs/15_SECURITY_BOUNDARIES.md). Never add real
credentials, customer code, or third-party exploit details to the repository.
Report vulnerabilities in this project per [SECURITY.md](SECURITY.md).

## Code of conduct

Participation is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
