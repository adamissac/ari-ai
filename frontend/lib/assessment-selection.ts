type ScopeOption = {
  id: string;
  name: string;
  targets: readonly { repo_id: string | null }[];
};

export function assessmentSelection(
  repoId: string,
  scopeId: string,
  repos: readonly { id: string }[],
  activeScopes: readonly ScopeOption[],
) {
  const selectedRepoId = repoId || (repos.length === 1 ? repos[0]?.id ?? '' : '');
  const applicableScopes = selectedRepoId
    ? activeScopes.filter(scope => scope.targets.some(target => target.repo_id === selectedRepoId))
    : [];
  const selectedScopeId = applicableScopes.some(scope => scope.id === scopeId)
    ? scopeId
    : applicableScopes.length === 1
      ? applicableScopes[0]?.id ?? ''
      : '';

  return {
    repoId: selectedRepoId,
    scopeId: selectedScopeId,
    scopes: applicableScopes,
  };
}
