# ADR 0011 — versioned standards integration

Status: proposed for review on the standards integration branch. Date: 2026-10-17.

Reuse Alan’s canonical catalogs, scoring port, shared 0.7.0 contracts and pure incident rules from PR #49. The backend owns persistence and project authorization; it resolves linked artifacts, independent Verify provenance, approved remediation and regression evidence before applying pure lifecycle rules. Shared validators additionally reject mismatched catalog metadata and fabricated numeric CVSS scores at persistence boundaries.

Finding.standards is the single finding classification record. Separate custom severity, CVSS, business priority, confidence, exploit status, simulation labels and human review status. Missing metrics produce no numeric score. Catalog chains are review leads; only reviewed contextual rules produce proposed ATT&CK labels. D3FEND proposals are not proof a control was deployed.

OWASP’s 2026 edition changes numbering. Preserve 2025 IDs for history and add a pinned 2026 catalog and matrix. Coverage concerns the platform itself; customer-app assessment remains unsupported. Partial and gap statuses remain explicit. Official reference: [OWASP 2026 announcement](https://genai.owasp.org/2026/09/01/owasp-genai-security-project-unveils-2026-top-10-for-llm-applications-new-agent-control-standard-and-sponsors-as-community-tops-30000-members/).

Incident states are local workflow labels mapped to CSF 2.0. An anomalous event is reported for triage; a human declares an incident. State changes record decisions and never execute infrastructure containment or recovery. Incident SSE is finite replay with Last-Event-ID. Rendered dashboard integration and live model execution are separate acceptance gates.

The alternatives were a second incompatible standards schema or a model-generated taxonomy/score. Reusing canonical work avoids schema divergence; deterministic validation and executed evidence preserve the project’s existing safety boundary.
