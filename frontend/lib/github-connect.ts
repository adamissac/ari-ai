import type { AccessibleRepository } from '@hackatl/frontend-transport';
import { api, idempotencyKey } from '@/lib/api';

/** One project per organization: found by name, created on the first connect. */
export async function projectFor(org: string): Promise<string> {
  const existing = (await api().projects()).items.find(p => p.name === org);
  if (existing) return existing.id;
  return (await api().createProject({ name: org, org_id: null, settings: null }, { idempotencyKey: idempotencyKey('project') })).id;
}

/** Connect a repository the user reached through the GitHub App; returns its repository id. */
export async function connectRepo(org: string, repo: AccessibleRepository): Promise<string> {
  if (repo.connected_repo_id) return repo.connected_repo_id;
  const pid = await projectFor(org);
  return (await api().connectRepository(pid, { full_name: repo.full_name, default_branch: repo.default_branch, installation_id: repo.installation_id })).id;
}
