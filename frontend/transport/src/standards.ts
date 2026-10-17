import type { Finding, StandardMapping, Incident } from './contracts.js';

/** Display text derived only from persisted records. Render as text, never innerHTML. */
export function mappingLabel(mapping: StandardMapping): string {
  return `${mapping.id} · ${mapping.name} (${mapping.catalog_version}) · ${mapping.observation} · ${mapping.review_status}`;
}

/** The CVSS v3.1 base score that sets the severity level (ADR-0012), or null when absent. */
export function severityBasis(finding: Finding): string | null {
  const v31 = finding.severity?.cvss_v31;
  if (!v31) return null;
  const unverified = v31.metric_evidence.filter(m => m.status === 'unverified').length;
  return `CVSS 3.1 (sets the severity level): ${v31.base_score} ${v31.rating} · ${v31.vector}`
    + (unverified ? ` · ${unverified} of 8 metrics unverified` : '');
}

export function findingStandards(finding: Finding): { labels: string[]; cvss: string; limitations: string[] } {
  const standards = finding.standards;
  const basis = severityBasis(finding);
  if (!standards) {
    return { labels: [], cvss: basis ?? 'Not assessed', limitations: ['No standards assessment recorded.'] };
  }
  const mappings = [ ...(standards.cwe ? [standards.cwe] : []), ...standards.attack, ...standards.d3fend ];
  const cvss = standards.cvss;
  const v40 = cvss?.complete
    ? `${cvss.assumptions.length ? "Provisional " : ""}CVSS ${cvss.version}: ${cvss.score} ${cvss.severity} · ${cvss.vector}`
    : `Unscored${cvss?.missing_metrics.length ? ` · missing ${cvss.missing_metrics.join(', ')}` : ''}`;
  return {
    labels: mappings.map(mappingLabel),
    // v4.0 is reported alongside the v3.1 score that sets the level; it never sets it.
    cvss: basis ? `${basis} | alongside: ${v40}` : v40,
    limitations: [ ...standards.unmapped, ...(cvss?.assumptions ?? []) ],
  };
}

export function incidentLabel(incident: Incident): string {
  return `${incident.simulated ? 'Simulated · ' : ''}${incident.title} · ${incident.state} · CSF ${incident.csf_function}`;
}
