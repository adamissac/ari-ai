import type { Assessment, AuthorizedScope } from '@hackatl/frontend-transport';
import { describe, expect, it } from 'vitest';
import { assessmentsForCommit, scopeBody, scopeStateFor } from '@/lib/real-assessment';
import { SCOPE_CHECK_CATEGORIES } from '@/lib/scope';

const scope = (
  id: string,
  repoId: string,
  status: AuthorizedScope['status'],
  expiresAt = '2026-12-01T00:00:00.000Z',
): AuthorizedScope => ({
  id,
  project_id: 'prj_test',
  name: `Authorize ${repoId}`,
  targets: [{ kind: 'sandbox_build', repo_id: repoId, build_recipe_ref: 'build_recipe.json', exposed_ports: [] }],
  allowed_check_categories: [],
  status,
  requested_by: 'usr_requester',
  approved_by: null,
  approved_at: null,
  expires_at: expiresAt,
  notes: null,
});

const assessment = (id: string, repoId: string | null, sha: string, createdAt: string): Assessment => ({
  id,
  project_id: 'prj_test',
  snapshot_id: null,
  commit_sha: sha,
  repo_id: repoId,
  scope_id: 'scp_test',
  trigger: 'manual',
  reassessment_request_id: null,
  state: 'CREATED',
  budget: { max_tokens: 1, max_usd: 1, max_wall_clock_s: 1 },
  usage: { input_tokens: 0, output_tokens: 0, cache_read_input_tokens: 0, usd: 0, sandbox_seconds: 0, llm_calls: 0, tool_calls: 0 },
  error: null,
  created_by: null,
  created_at: createdAt,
  updated_at: createdAt,
  completed_at: null,
});

describe('scopeBody', () => {
  it('builds the default authorization scope with explicit nullable and empty fields', () => {
    const now = new Date('2026-01-01T12:00:00.000Z');
    expect(scopeBody('repo_123', now)).toEqual({
      name: 'Authorize repo_123',
      targets: [{ kind: 'sandbox_build', repo_id: 'repo_123', build_recipe_ref: 'build_recipe.json', exposed_ports: [] }],
      allowed_check_categories: [...SCOPE_CHECK_CATEGORIES],
      expires_at: '2026-01-31T12:00:00.000Z',
      notes: null,
    });
  });
});

describe('scopeStateFor', () => {
  const now = new Date('2026-01-01T00:00:00.000Z');

  it('prefers an active covering scope over pending, and newest first within a status', () => {
    const newerActive = scope('scp_new', 'repo_123', 'active');
    const olderActive = scope('scp_old', 'repo_123', 'active');
    const pending = scope('scp_pending', 'repo_123', 'pending');
    expect(scopeStateFor([pending, newerActive, olderActive], 'repo_123', now)).toEqual({ kind: 'active', scope: newerActive });
    expect(scopeStateFor([newerActive, olderActive], 'repo_123', now)).toEqual({ kind: 'active', scope: newerActive });
  });

  it('ignores expired and other-repository scopes, then returns the newest covering pending scope', () => {
    const expired = scope('scp_expired', 'repo_123', 'active', '2025-12-31T23:59:59.999Z');
    const otherRepo = scope('scp_other', 'repo_other', 'active');
    const newestPending = scope('scp_pending_new', 'repo_123', 'pending');
    const olderPending = scope('scp_pending_old', 'repo_123', 'pending');
    expect(scopeStateFor([expired, otherRepo, newestPending, olderPending], 'repo_123', now)).toEqual({ kind: 'pending', scope: newestPending });
    expect(scopeStateFor([expired, otherRepo], 'repo_123', now)).toEqual({ kind: 'none' });
  });
});

describe('assessmentsForCommit', () => {
  it('filters to the repository and commit, newest first', () => {
    const sha = 'a'.repeat(40);
    const items = [
      assessment('asm_old', 'repo_123', sha, '2026-01-01T00:00:00.000Z'),
      assessment('asm_other_repo', 'repo_other', sha, '2026-01-03T00:00:00.000Z'),
      assessment('asm_other_commit', 'repo_123', 'b'.repeat(40), '2026-01-04T00:00:00.000Z'),
      assessment('asm_new', 'repo_123', sha, '2026-01-02T00:00:00.000Z'),
      assessment('asm_missing_repo', null, sha, '2026-01-05T00:00:00.000Z'),
    ];
    expect(assessmentsForCommit(items, 'repo_123', sha).map(item => item.id)).toEqual(['asm_new', 'asm_old']);
  });
});
