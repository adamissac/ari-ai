export type FindingGroup = 'hypothesis' | 'open' | 'fixed' | 'closed';

const CLOSED = new Set(['refuted', 'accepted_risk', 'closed']);
const FIXED = new Set(['verified', 'hardened']);

/** How the findings list groups a status. Open is not the same as confirmed; a verified fix is not open. */
export function findingGroup(status: string): FindingGroup {
  if (status === 'hypothesis') return 'hypothesis';
  if (CLOSED.has(status)) return 'closed';
  if (FIXED.has(status)) return 'fixed';
  return 'open';
}

export function findingGroupCounts(findings: readonly { status: string }[]): Record<FindingGroup, number> {
  const counts: Record<FindingGroup, number> = { hypothesis: 0, open: 0, fixed: 0, closed: 0 };
  for (const finding of findings) counts[findingGroup(finding.status)]++;
  return counts;
}

/** A fix that independent tests accepted. */
export function isFixed(status: string): boolean {
  return FIXED.has(status);
}

/**
 * Finer buckets, derived from `findingGroup` so every view agrees:
 * - `untested`: an unconfirmed suspicion (group hypothesis)
 * - `dismissed`: refuted, accepted risk or closed (group closed)
 * - `fixed`: findings whose fix independent tests accepted (group fixed)
 * - `inconclusive`: a test ran but could not decide; neither confirmed nor ruled out
 * - `confirmed`: everything else still open (validated, diagnosed, patch proposed or rejected, unresolved, stale)
 */
export type FindingBucket = 'untested' | 'dismissed' | 'fixed' | 'inconclusive' | 'confirmed';

export function findingBucket(status: string): FindingBucket {
  const group = findingGroup(status);
  if (group === 'hypothesis') return 'untested';
  if (group === 'closed') return 'dismissed';
  if (group === 'fixed') return 'fixed';
  if (status === 'inconclusive') return 'inconclusive';
  return 'confirmed';
}

/** Count findings per bucket, optionally for one kind. */
export function bucketCounts(findings: readonly { kind: string; status: string }[], kind?: string): Record<FindingBucket, number> {
  const counts: Record<FindingBucket, number> = { untested: 0, dismissed: 0, fixed: 0, inconclusive: 0, confirmed: 0 };
  for (const f of findings) if (!kind || f.kind === kind) counts[findingBucket(f.status)]++;
  return counts;
}

/** What one review run of a commit turned up, from its persisted findings. */
export interface CommitOutcome { needsFix: number; fixed: number; unproven: number }

export function commitOutcome(findings: readonly { assessment_id: string; status: string }[], assessmentId: string): CommitOutcome {
  const out: CommitOutcome = { needsFix: 0, fixed: 0, unproven: 0 };
  for (const f of findings) {
    if (f.assessment_id !== assessmentId) continue;
    const bucket = findingBucket(f.status);
    if (bucket === 'confirmed') out.needsFix++;
    else if (bucket === 'fixed') out.fixed++;
    else if (bucket === 'untested' || bucket === 'inconclusive') out.unproven++;
  }
  return out;
}

/** Ari proved a problem or fixed one in this run; untested suspicions alone do not count. */
export function foundSomething(outcome: CommitOutcome): boolean {
  return outcome.needsFix > 0 || outcome.fixed > 0;
}

/** Why a proven problem is still open, in plain words, from the statuses the backend sets. */
export const OPEN_REASON: Record<string, string> = {
  validated: 'proven by a test; fix not started (it starts after approval, or at once when fix delivery is automatic)',
  diagnosed: 'cause found and fix planned; not written yet (approval is pending or was declined)',
  patch_proposed: 'fix written; waiting for approval or its tests',
  patch_rejected: 'Ari tried 4 different fixes and each failed independent tests; needs a manual fix',
  unresolved: 'Ari could not produce a fix in 4 attempts; needs a manual fix',
  needs_recheck: 'marked for a recheck',
};
