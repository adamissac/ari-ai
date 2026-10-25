import { describe, expect, it } from 'vitest';
import { commitFreshness } from '@/lib/commit-freshness';

describe('commit freshness', () => {
  const latestSha = 'a'.repeat(40);
  const selectedSha = 'b'.repeat(40);

  it('returns null when the recent commits are unavailable or empty', () => {
    expect(commitFreshness(undefined, selectedSha)).toBeNull();
    expect(commitFreshness([], selectedSha)).toBeNull();
  });

  it('identifies the latest commit', () => {
    expect(commitFreshness([{ sha: latestSha }, { sha: selectedSha }], latestSha))
      .toEqual({ kind: 'latest' });
  });

  it('marks a non-latest commit in the recent list as stale', () => {
    const recent = [
      { sha: latestSha },
      { sha: 'c'.repeat(40) },
      { sha: 'd'.repeat(40) },
      { sha: selectedSha },
    ];
    expect(commitFreshness(recent, selectedSha))
      .toEqual({ kind: 'stale', latestSha });
  });

  it('matches a short SHA prefix and marks it stale', () => {
    expect(commitFreshness([{ sha: latestSha }, { sha: selectedSha }], selectedSha.slice(0, 8)))
      .toEqual({ kind: 'stale', latestSha });
  });

  it('marks a commit outside the recent list as stale', () => {
    expect(commitFreshness([{ sha: latestSha }, { sha: selectedSha }], 'f'.repeat(40)))
      .toEqual({ kind: 'stale', latestSha });
  });
});
