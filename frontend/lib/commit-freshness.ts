export type CommitFreshness =
  | { kind: 'latest' }
  | { kind: 'stale'; latestSha: string };

export function commitFreshness(
  recent: { sha: string }[] | undefined,
  sha: string,
): CommitFreshness | null {
  if (!recent?.length) return null;
  const latest = recent[0];
  if (!latest) return null;

  const index = recent.findIndex(commit => commit.sha === sha || commit.sha.startsWith(sha));
  if (index === 0) return { kind: 'latest' };
  return { kind: 'stale', latestSha: latest.sha };
}
