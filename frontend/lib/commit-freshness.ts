export type CommitFreshness =
  | { kind: 'latest' }
  | { kind: 'behind'; count: number; latestSha: string }
  | { kind: 'older'; latestSha: string };

export function commitFreshness(
  recent: { sha: string }[] | undefined,
  sha: string,
): CommitFreshness | null {
  if (!recent?.length) return null;
  const latest = recent[0];
  if (!latest) return null;

  const index = recent.findIndex(commit => commit.sha === sha || commit.sha.startsWith(sha));
  if (index === 0) return { kind: 'latest' };
  if (index > 0) return { kind: 'behind', count: index, latestSha: latest.sha };
  return { kind: 'older', latestSha: latest.sha };
}
