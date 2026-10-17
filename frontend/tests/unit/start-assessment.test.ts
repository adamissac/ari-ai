import { describe, expect, it } from 'vitest';
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
