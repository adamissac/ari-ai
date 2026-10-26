import { describe, expect, it } from 'vitest';
import type { Repository } from '@hackatl/frontend-transport';
import { resolveSelectedRepo } from '@/lib/selected-repo';

const repos = [
  { id: 'repo-1', full_name: 'acme/payments', default_branch: 'main' },
  { id: 'repo-2', full_name: 'acme/store', default_branch: 'trunk' },
] as Repository[];

describe('resolveSelectedRepo', () => {
  it('prefers a valid URL repository over stored selection', () => {
    expect(resolveSelectedRepo(repos, 'repo-2', 'repo-1')).toBe(repos[1]);
  });

  it('falls through invalid ids to the first available repository', () => {
    expect(resolveSelectedRepo(repos, 'unknown', 'also-unknown')).toBe(repos[0]);
  });

  it('uses the stored selection when no valid URL id exists', () => {
    expect(resolveSelectedRepo(repos, null, 'repo-2')).toBe(repos[1]);
    expect(resolveSelectedRepo(repos, 'unknown', 'repo-2')).toBe(repos[1]);
  });

  it('returns null when the project has no repositories', () => {
    expect(resolveSelectedRepo([], null, null)).toBeNull();
  });
});
