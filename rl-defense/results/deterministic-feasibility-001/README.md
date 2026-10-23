# Deterministic feasibility 001

One preregistered pass, no retries or replacement cases. Execution source:
`73f42092a6d73f29d3b846b3aa170605ebce4fbd` (see full identity in EVIDENCE.json). Protocol SHA256:
`2a194354f5d8c5cb2fe3d058cc654d0180469de34336ec22795b812640dc68e5`.
The protocol/source were committed and pushed before execution. 54 in-process HTTP
requests: 18 authored cases per fixed policy (7 unauthorized, 2 owner, 3 delegate,
6 unknown). Owner approved zero unauthorized successes and zero valid denials.

- Exact-resource guard: 0/7 unauthorized successes, 0/2 owner denials,
  0/3 delegated denials; all 6 unknown contexts abstained (503), none forwarded.
- Unguarded: 7/7 unauthorized successes; unknown contexts also forwarded.
- Blanket deny: 0/7 unauthorized successes, but 2/2 owner and 3/3 delegated denials.

All request statuses/forwarding observations are retained in RESULT.json. Its digest,
source commit and protocol digest are in EVIDENCE.json. Runtime dependency versions
are recorded. No hidden traffic-generator attack labels enter the guard.

The authored fixture always serves one synthetic resource and receives trusted
fixture context; it does not extract identity/ownership from a real application.
Grant renewal/revocation and stale/unknown context are separate fixed cases, not
concurrent application-state changes. Repetition/principal isolation additionally
have unit coverage. Results prove this finite guard behavior only. No statistical
population estimate, held-out RL scenario, control lifecycle, production integration,
model training, checkpoint promotion or customer traffic is claimed.

Decision: proceed to independently specified application-context integration checks
before any broader feasibility claim. A deterministic authorization repair remains
preferable if it solves the target problem. The no-go for constrained DDQN/CQL remains.

Review limitation: the original runner checked elapsed time before each request but
not after the final response. It did not record an elapsed duration, so strict
post-response compute-limit compliance cannot be certified from these artifacts.
A later runner revision checks after every response and has an explicit final-request
overrun regression. This original comparison was not rerun or replaced; its numerical
finite-case results and source/protocol identities remain unchanged.
