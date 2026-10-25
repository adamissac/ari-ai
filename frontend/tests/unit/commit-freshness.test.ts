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

  it('returns the number of commits behind the latest', () => {
    const recent = [
      { sha: latestSha },
      { sha: 'c'.repeat(40) },
      { sha: 'd'.repeat(40) },
      { sha: selectedSha },
    ];
    expect(commitFreshness(recent, selectedSha))
      .toEqual({ kind: 'behind', count: 3, latestSha });
  });

  it('matches a short SHA prefix', () => {
    expect(commitFreshness([{ sha: latestSha }, { sha: selectedSha }], selectedSha.slice(0, 8)))
      .toEqual({ kind: 'behind', count: 1, latestSha });
  });

  it('marks a commit outside the recent list as older', () => {
    expect(commitFreshness([{ sha: latestSha }, { sha: selectedSha }], 'f'.repeat(40)))
      .toEqual({ kind: 'older', latestSha });
  });
});
