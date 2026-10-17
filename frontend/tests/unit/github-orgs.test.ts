import { describe, expect, it } from 'vitest';
import { groupByOrg, repoName } from '@/lib/github-orgs';

const repo = (full_name: string, extra: { private?: boolean; connected?: string } = {}) => ({
  full_name,
  installation_id: 1,
  default_branch: 'main',
  private: extra.private ?? false,
  connected_repo_id: extra.connected ?? null,
});

describe('groupByOrg', () => {
  it('groups by owner, sorted, with connected and private counts', () => {
    const orgs = groupByOrg([repo('zeta/api'), repo('Acme/web', { private: true }), repo('Acme/api', { connected: 'repo_1' })]);
    expect(orgs.map(o => o.login)).toEqual(['Acme', 'zeta']);
    expect(orgs[0]!.repos.map(r => r.full_name)).toEqual(['Acme/api', 'Acme/web']);
    expect(orgs[0]!.connected).toBe(1);
    expect(orgs[0]!.private).toBe(1);
  });

  it('is empty for no repositories', () => {
    expect(groupByOrg([])).toEqual([]);
  });
});

describe('repoName', () => {
  it('drops the owner', () => {
    expect(repoName('acme/shop')).toBe('shop');
  });
});
