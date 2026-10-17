import type { AccessibleRepository } from '@hackatl/frontend-transport';

export interface GitHubOrg {
  login: string;
  repos: AccessibleRepository[];
  connected: number;
  private: number;
}

/** Group the repositories the App can see by owner (organization or personal account). */
export function groupByOrg(items: readonly AccessibleRepository[]): GitHubOrg[] {
  const byOwner = new Map<string, AccessibleRepository[]>();
  for (const repo of items) {
    const owner = repo.full_name.split('/')[0]!;
    byOwner.set(owner, [...(byOwner.get(owner) ?? []), repo]);
  }
  return [...byOwner.entries()]
    .map(([login, repos]) => ({
      login,
      repos: [...repos].sort((a, b) => a.full_name.localeCompare(b.full_name)),
      connected: repos.filter(r => r.connected_repo_id).length,
      private: repos.filter(r => r.private).length,
    }))
    .sort((a, b) => a.login.localeCompare(b.login, undefined, { sensitivity: 'base' }));
}

/** The repository name without its owner, for display under an organization. */
export function repoName(fullName: string): string {
  return fullName.slice(fullName.indexOf('/') + 1);
}
