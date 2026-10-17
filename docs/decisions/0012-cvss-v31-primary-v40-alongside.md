# ADR-0012: CVSS v3.1 base score sets the platform severity level now; v4.0 alongside, primary later

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-10-17 |
| Deciders | Alan (owner decision recorded in session); team ratification pending |
| Related | RQ-016, ADR-0011, SEC-008 (Trace), `standards/standards/cvss31.py`, `standards/standards/cvss4.py`, `security-agents/security_agents/agents/trace.py` |

## Context
Trace previously set the severity level from a custom four-factor rubric. ADR-0011
added an optional CVSS v4.0 assessment that stays provisional and never sets the
level. Judges and users recognise CVSS v3.1 scores (NVD publishes them for most
CVEs), and v3.1 has a short, fully specified equation with a published Roundup
function that we can check against real NVD vector and score pairs offline.

The model must never set a severity level or a score. A CVSS base score measures
technical severity, not business risk.

## Decision
1. Trace proposes the eight CVSS v3.1 base metrics (AV, AC, PR, UI, S, C, I, A).
   Each metric cites a file span or the executed validation run; a metric without
   a citation is recorded with status `unverified`.
2. Code computes the v3.1 vector, base score (FIRST specification, including the
   Appendix A Roundup) and qualitative rating. The platform severity level is
   derived from that rating. The record carries `score_kind = "CVSS v3.1 base
   score only (severity, not risk)"` and `level_source`.
3. The optional v4.0 assessment from ADR-0011 stays alongside, unchanged: complete
   metrics backed by the executed run, labelled provisional, never setting the
   level.
4. The calculator is checked against 34 NVD vector and score pairs pinned with
   sha256 plus property tests (monotonicity, bounds, Roundup behaviour).
5. Revisit and make v4.0 primary once v4.0 metrics are reviewed by a human for
   at least one real finding and the UI shows both scores.

## Options considered
| Option | Pros | Cons |
|---|---|---|
| Custom rubric only | Simple, already built | Not a recognised standard; hard to explain to judges |
| CVSS v4.0 primary now | Current FIRST version | Eleven metrics, larger lookup; fewer published real-world scores to test against; metrics remain provisional |
| CVSS v3.1 primary, v4.0 alongside (chosen) | Recognised, fully specified, tested against NVD pairs; keeps the v4.0 work | Two scores to explain; v3.1 is the older version |

## Consequences
- The demo finding (payments-lite, CWE-639) scores `CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N`,
  base score 6.5, rating medium. `examples/payments-lite/labels.yaml` labels it high.
  The difference is expected: base scores measure severity, not risk. A test records it.
- `SeverityAssessment` gains adapter fields in `security-agents` (`cvss_version`,
  `cvss_vector`, `cvss_base_score`, `cvss_rating`, `score_kind`, `level_source`,
  `metric_evidence`). `shared.standards.CVSSAssessment` remains v4.0 only; a v3.1
  shared field is proposed to Srihith and is not yet accepted.
- The NVD terms page could not be read (Cloudflare challenge), so the NVD vector
  file is marked UNVERIFIED for licence terms; only CVE ids, vectors and scores are stored.

## Revisit when
A human has reviewed v4.0 metrics on a real finding, the UI renders both scores,
or `shared` accepts a v3.1 field.
