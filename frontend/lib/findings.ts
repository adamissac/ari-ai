export type FindingGroup = 'hypothesis' | 'open' | 'closed';

const CLOSED = new Set(['refuted', 'accepted_risk', 'closed']);

/** How the findings list groups a status. Open is not the same as confirmed. */
export function findingGroup(status: string): FindingGroup {
  if (status === 'hypothesis') return 'hypothesis';
  if (CLOSED.has(status)) return 'closed';
  return 'open';
}

export const FINDING_GROUP_NOTE =
  'Open is everything still on the record that is not an untested hypothesis and not refuted, accepted, or closed. That includes inconclusive results and rejected fixes. It is not a list of confirmed exploits.';
