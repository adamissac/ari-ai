export type FindingGroup = 'hypothesis' | 'open' | 'closed';

const CLOSED = new Set(['refuted', 'accepted_risk', 'closed']);
const FIXED = new Set(['verified', 'hardened']);

/** How the findings list groups a status. Open is not the same as confirmed. */
export function findingGroup(status: string): FindingGroup {
  if (status === 'hypothesis') return 'hypothesis';
  if (CLOSED.has(status)) return 'closed';
  return 'open';
}

/** A fix that independent tests accepted. */
export function isFixed(status: string): boolean {
  return FIXED.has(status);
}

/**
 * Finer buckets, derived from `findingGroup` so every view agrees:
 * - `untested`: an unconfirmed suspicion (group hypothesis)
 * - `dismissed`: refuted, accepted risk or closed (group closed)
 * - `fixed`: open-group findings whose fix independent tests accepted
 * - `inconclusive`: a test ran but could not decide; neither confirmed nor ruled out
 * - `confirmed`: everything else still open (validated, diagnosed, patch proposed or rejected, unresolved, stale)
 */
export type FindingBucket = 'untested' | 'dismissed' | 'fixed' | 'inconclusive' | 'confirmed';

export function findingBucket(status: string): FindingBucket {
  const group = findingGroup(status);
  if (group === 'hypothesis') return 'untested';
  if (group === 'closed') return 'dismissed';
  if (isFixed(status)) return 'fixed';
  if (status === 'inconclusive') return 'inconclusive';
  return 'confirmed';
}

/** Count findings per bucket, optionally for one kind. */
export function bucketCounts(findings: readonly { kind: string; status: string }[], kind?: string): Record<FindingBucket, number> {
  const counts: Record<FindingBucket, number> = { untested: 0, dismissed: 0, fixed: 0, inconclusive: 0, confirmed: 0 };
  for (const f of findings) if (!kind || f.kind === kind) counts[findingBucket(f.status)]++;
  return counts;
}

export const FINDING_GROUP_NOTE =
  'Open is everything still on the record that is not an untested hypothesis and not refuted, accepted, or closed. That includes inconclusive results, rejected fixes and accepted fixes. It is not a list of confirmed exploits.';
