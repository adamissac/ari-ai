import type { Finding, StandardMapping, Incident } from './contracts.js';

/** Display text derived only from persisted records. Render as text, never innerHTML. */
export function mappingLabel(mapping: StandardMapping): string {
  return `${mapping.id} · ${mapping.name} (${mapping.catalog_version}) · ${mapping.observation} · ${mapping.review_status}`;
}

export function findingStandards(finding: Finding): { labels: string[]; cvss: string; limitations: string[] } {
  const standards = finding.standards;
  if (!standards) return { labels: [], cvss: 'Not assessed', limitations: ['No standards assessment recorded.'] };
  const mappings = [ ...(standards.cwe ? [standards.cwe] : []), ...standards.attack, ...standards.d3fend ];
  const cvss = standards.cvss;
  return {
    labels: mappings.map(mappingLabel),
    cvss: cvss?.complete
      ? `${cvss.assumptions.length ? "Provisional " : ""}CVSS ${cvss.version}: ${cvss.score} ${cvss.severity} · ${cvss.vector}`
      : `Unscored${cvss?.missing_metrics.length ? ` · missing ${cvss.missing_metrics.join(', ')}` : ''}`,
    limitations: [ ...standards.unmapped, ...(cvss?.assumptions ?? []) ],
  };
}

export function incidentLabel(incident: Incident): string {
  return `${incident.simulated ? 'Simulated · ' : ''}${incident.title} · ${incident.state} · CSF ${incident.csf_function}`;
}
