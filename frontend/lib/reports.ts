import type { StreamEvent } from '@hackatl/frontend-transport';

export interface ReportLink { label: string; href: string; testid: string }

const ARTIFACT_ID = /^art_[A-Za-z0-9]{8,64}$/;
const REPORTS = [
  { key: 'sarif_artifact_id', label: 'SARIF report', testid: 'report-sarif' },
  { key: 'roe_artifact_id', label: 'Rules of engagement', testid: 'report-roe' },
] as const;

/** Download links for the standards reports a run stored; ids come only from its persisted events. */
export function reportLinks(events: StreamEvent[]): ReportLink[] {
  const links: ReportLink[] = [];
  for (const { key, label, testid } of REPORTS) {
    const id = events.map(e => e.data[key]).findLast(v => typeof v === 'string' && ARTIFACT_ID.test(v));
    if (typeof id === 'string') links.push({ label, href: `/api/v1/artifacts/${id}`, testid });
  }
  return links;
}
