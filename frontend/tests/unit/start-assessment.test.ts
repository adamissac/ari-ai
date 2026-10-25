import { describe, expect, it } from 'vitest';
import { assessmentSelection } from '@/lib/assessment-selection';
import { START_ASSESSMENT_NOTE } from '@/lib/start-assessment';

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
});
