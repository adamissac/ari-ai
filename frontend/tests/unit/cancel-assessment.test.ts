import { describe, expect, it } from 'vitest';
import { CANCEL_ASSESSMENT_NOTE, cancelAssessmentResult } from '@/lib/cancel-assessment';

describe('cancel assessment note', () => {
  it('distinguishes queued stop from in-flight stop, and does not claim findings are deleted', () => {
    expect(CANCEL_ASSESSMENT_NOTE).toContain('has not started yet');
    expect(CANCEL_ASSESSMENT_NOTE).toContain('requests a stop');
    expect(CANCEL_ASSESSMENT_NOTE).toContain('current step may finish');
    expect(CANCEL_ASSESSMENT_NOTE).toContain('does not delete findings');
    expect(CANCEL_ASSESSMENT_NOTE).toContain('undo work already recorded');
  });

  it('names the two cancel outcomes from the API cancelled flag', () => {
    expect(cancelAssessmentResult(true)).toContain('before any worker started');
    expect(cancelAssessmentResult(false)).toContain('Stop requested');
    expect(cancelAssessmentResult(false)).toContain('current step may finish');
  });
});
