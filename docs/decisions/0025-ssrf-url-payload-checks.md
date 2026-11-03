# ADR-0025: SSRF check templates may carry URL payloads (proposed)

- Status: Proposed (owner review: Adam; **security-boundary review required before the
  SSRF template is marked `reviewed_by` and allowed to run live**)
- Date: 2026-11-03
- Context: The Probe check library (SEC-005) renders a pytest module per template and runs
  it in the check-runner profile. `security_agents.checks.review_packet` lints every
  rendered module and fails the packet if it contains a forbidden token. The set includes
  `http://` and `https://`, so that a check can never reach an external host itself.

  An SSRF check (CWE-918) must send the target a URL that names an internal or
  cloud-metadata destination (`http://169.254.169.254/…`, `http://127.0.0.1/`,
  `http://localhost/`) and assert the endpoint refuses it. That URL is **request data the
  target receives**, not a host the check connects to. The blanket `http://` ban makes
  such a template impossible to express.

  The run network is already `target-only` with no egress ([ADR-0006], docs/15 §4), so an
  SSRF check cannot observe a *reached* host anyway; the only sound signal is that the
  endpoint validates the destination and refuses a loopback/metadata URL with a non-auth
  4xx, never attempting the fetch.

## Decision

- `CheckTemplateMeta` gains `emits_url_payloads: bool = False`. A template sets it only
  when its sole use of a URL scheme is a payload sent to the target as request data.
- The review packet replaces `FORBIDDEN_TOKENS` with `URL_PAYLOAD_FORBIDDEN` (the same set
  minus `http://` and `https://`) **only** for a non-harness template that declares
  `emits_url_payloads`. Every other forbidden token stays banned for it: `subprocess`,
  `socket`, `requests.`, `os.system`, `eval(`, `exec(`. The import allowlist is unchanged,
  so the check still opens no socket, spawns no process, and imports nothing extra — it
  drives the target through the same in-process/HTTP client as every other check.
- The first such template is `input_validation.ssrf@1` (`input_validation.ssrf` scope
  category). It asserts the endpoint refuses internal/metadata destinations with a 4xx
  that is not `401`; a vulnerable endpoint that accepts the URL (or, with no egress,
  answers 5xx when it attempts the fetch) fails the check. A `401` skips as inconclusive.

## Consequences

- The deterministic network boundaries are untouched: the sandbox network policy, the
  egress ban, and the socket/process bans on rendered checks all still hold and are
  enforced in code, not by this lint. This ADR narrows one belt-and-suspenders lint for a
  specific, declared template class.
- The SSRF template, like every template in the library, keeps
  `reviewed_by="security-owner:pending-human-signoff"` and cannot run until a human signs
  off on its renderer hash. The relaxation is visible in the review packet, which lists
  the template's `emits_url_payloads` effect and the exact tokens still forbidden.
- A template must not set `emits_url_payloads` to smuggle in a real outbound call; the
  socket/`requests.`/`subprocess` bans remain the defence against that and are what the
  human reviewer checks.

[ADR-0006]: 0006-docker-sandbox-no-network-default.md
