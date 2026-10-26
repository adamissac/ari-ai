import type { AccessibleRepository } from '@hackatl/frontend-transport';
import { api, idempotencyKey } from '@/lib/api';

/**
 * The project a newly connected repository from `org` joins. Identity first: the project that
 * already holds another of this owner's repositories (a project can be renamed; its repositories
 * stay put). Then a project still named after the owner (projects created before this rule), then
 * a new one.
 */
export async function projectFor(org: string): Promise<string> {
  const owner = org.toLowerCase();
  const sibling = (await api().githubRepositories()).items
    .find(repo => repo.connected_repo_id && repo.full_name.slice(0, repo.full_name.indexOf('/')).toLowerCase() === owner);
  if (sibling) return projectForRepository(sibling.connected_repo_id!);
  const existing = (await api().projects()).items.find(p => p.name === org);
  if (existing) return existing.id;
  return (await api().createProject({ name: org, org_id: null, settings: null }, { idempotencyKey: idempotencyKey('project') })).id;
}

/** The Ari repository id while Ari may still read it; a disconnected row needs reconnecting first. */
export function liveRepoId(repo: AccessibleRepository): string | null {
  return repo.disconnected ? null : repo.connected_repo_id;
}

/**
 * Connect a repository the user reached through the GitHub App; returns its repository id.
 * A disconnected one is reconnected, which re-checks the GitHub grant on the server.
 */
export async function connectRepo(org: string, repo: AccessibleRepository): Promise<string> {
  if (repo.connected_repo_id && repo.disconnected) {
    await api().reconnectRepository(repo.connected_repo_id);
    return repo.connected_repo_id;
  }
  if (repo.connected_repo_id) return repo.connected_repo_id;
  const pid = await projectFor(org);
  return (await api().connectRepository(pid, { full_name: repo.full_name, default_branch: repo.default_branch, installation_id: repo.installation_id })).id;
}

/** The repository's own project, as the API records it (no scan of every project). */
export async function projectForRepository(repoId: string, signal?: AbortSignal): Promise<string> {
  return (await api().repository(repoId, signal ? { signal } : undefined)).project_id;
}
