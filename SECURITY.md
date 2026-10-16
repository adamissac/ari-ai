# Security Policy

This repository will contain tooling that analyzes, attacks (in sandboxes), and
patches software. We hold ourselves to a high standard for our own security.

## Supported versions

No released versions exist yet (Phase 0). Once releases begin, the latest `main`
and the most recent tagged release will be supported.

## Reporting a vulnerability in this project

- **Do not open a public issue.**
- Use GitHub's **private vulnerability reporting** for this repository
  ("Security" tab → "Report a vulnerability"). *Enabling this setting is tracked as
  `INFRA-002`; until it is enabled, contact a maintainer privately.*
- Include: affected component, version/commit, reproduction steps, impact, and any
  suggested fix.
- We aim to acknowledge within 3 business days and to provide a remediation plan
  within 14 days. These are targets, not guarantees, for a small team.

## Scope of our own security testing

The platform's security agents are designed to test **only** targets registered
in an authorized scope with a human approver, inside isolated sandboxes
([docs/15_SECURITY_BOUNDARIES.md](docs/15_SECURITY_BOUNDARIES.md)). If you find a way
to make the platform test an unauthorized target, escape a sandbox, widen agent
permissions, or get model output to bypass an approval, that is a **critical**
vulnerability — please report it.

## Handling of security information

- Findings from customer or third-party systems are confidential and never
  committed to this repo, posted in issues, or used in public demos.
- Demo vulnerabilities live only in deliberately vulnerable fixtures under
  `examples/` that we own.
- Secrets must never be committed. If one is, rotate it immediately, then purge it
  from history; notify maintainers.

## Responsible use

This software must not be used to attack systems without explicit, written
authorization from their owner.
