import { describe, expect, it } from 'vitest';
import { assessmentSelection } from '@/lib/assessment-selection';
import { START_ASSESSMENT_NOTE } from '@/lib/start-assessment';
import { effectiveScopeStatus } from '@/lib/status';

describe('start assessment note', () => {
  it('names the enqueue and does not claim merge, deploy, or a secure finish', () => {
    expect(START_ASSESSMENT_NOTE).toContain('enqueues work');
    expect(START_ASSESSMENT_NOTE).toContain('human-approved scope');
    expect(START_ASSESSMENT_NOTE).toContain('does not merge code');
    expect(START_ASSESSMENT_NOTE).toContain('deploy');
    expect(START_ASSESSMENT_NOTE).toContain('prove the application is secure');
  });
});

describe('assessment selection defaults', () => {
  it('preselects the sole repository and its only applicable active scope', () => {
    const selection = assessmentSelection('', '', [{ id: 'rep_one' }], [
      { id: 'scope_one', name: 'One', targets: [{ repo_id: 'rep_one' }] },
      { id: 'scope_other', name: 'Other', targets: [{ repo_id: 'rep_two' }] },
    ]);

    expect(selection.repoId).toBe('rep_one');
    expect(selection.scopeId).toBe('scope_one');
    expect(selection.scopes.map(scope => scope.id)).toEqual(['scope_one']);
  });

  it('does not preselect an expired scope as the only covering scope', () => {
    const now = new Date('2026-10-26T00:00:00Z');
    const scopes = [
      {
        id: 'scope_expired',
        name: 'Expired',
        status: 'active' as const,
        expires_at: '2000-01-01T00:00:00Z',
        targets: [{ repo_id: 'rep_one' }],
      },
    ];
    const activeScopes = scopes.filter(scope => effectiveScopeStatus(scope, now) === 'active');
    const selection = assessmentSelection('', '', [{ id: 'rep_one' }], activeScopes);

    expect(selection.scopeId).toBe('');
    expect(selection.scopes).toEqual([]);
  });
});
