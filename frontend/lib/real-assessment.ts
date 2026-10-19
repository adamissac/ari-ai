import type { Assessment, AuthorizedScope, ScopeCreate } from '@hackatl/frontend-transport';
import { SCOPE_CHECK_CATEGORIES } from '@/lib/scope';

const THIRTY_DAYS_MS = 30 * 24 * 60 * 60 * 1000;

export function scopeBody(repoId: string, now: Date): ScopeCreate {
  return {
    name: `Authorize ${repoId}`,
    targets: [{ kind: 'sandbox_build', repo_id: repoId, build_recipe_ref: 'build_recipe.json', exposed_ports: [] }],
    allowed_check_categories: [...SCOPE_CHECK_CATEGORIES],
    expires_at: new Date(now.getTime() + THIRTY_DAYS_MS).toISOString(),
    notes: null,
  };
}

export function scopeStateFor(
  scopes: AuthorizedScope[],
  repoId: string,
  now: Date,
): { kind: 'active'; scope: AuthorizedScope } | { kind: 'pending'; scope: AuthorizedScope } | { kind: 'none' } {
  const coversRepo = (scope: AuthorizedScope) => scope.targets.some(target => target.repo_id === repoId);
  const active = scopes.find(scope => scope.status === 'active' && coversRepo(scope) && Date.parse(scope.expires_at) > now.getTime());
  if (active) return { kind: 'active', scope: active };

  const pending = scopes.find(scope => scope.status === 'pending' && coversRepo(scope) && Date.parse(scope.expires_at) > now.getTime());
  return pending ? { kind: 'pending', scope: pending } : { kind: 'none' };
}

export function assessmentsForCommit(items: Assessment[], repoId: string, sha: string): Assessment[] {
  return items
    .filter(item => item.repo_id === repoId && item.commit_sha === sha)
    .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
}

/** Owners may approve their own scope only when every target is sandbox-bound. */
export function isSandboxOnlyScope(scope: AuthorizedScope): boolean {
  return scope.targets.length > 0 && scope.targets.every(target => target.kind === 'sandbox_build');
}
