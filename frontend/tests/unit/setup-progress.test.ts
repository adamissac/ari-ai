import { describe, expect, it } from 'vitest';
import { answerSetupQuestion, canVisitSetupQuestion, isSetupComplete, parseSetupProgress, resumeSetupQuestion, setupProgressKey } from '@/lib/setup-progress';

describe('setup progress', () => {
  it('resumes at the first unanswered question and prevents skipping ahead', () => {
    let progress = parseSetupProgress(null);
    expect(resumeSetupQuestion(progress)).toBe(1);
    expect(canVisitSetupQuestion(progress, 2)).toBe(false);
    progress = answerSetupQuestion(progress, 'readiness', true);
    expect(resumeSetupQuestion(progress)).toBe(2);
    expect(canVisitSetupQuestion(progress, 1)).toBe(true);
    expect(canVisitSetupQuestion(progress, 2)).toBe(true);
    expect(canVisitSetupQuestion(progress, 3)).toBe(false);
  });

  it('restores answers and completion from storage', () => {
    const progress = parseSetupProgress(JSON.stringify({ answers: { readiness: true, strictness: 'balanced' }, complete: true }));
    expect(resumeSetupQuestion(progress)).toBe(3);
    expect(isSetupComplete(progress, false)).toBe(true);
    expect(setupProgressKey('project', 'repo')).toBe('ari-setup:project:repo');
  });

  it('treats an existing assessment as completed setup', () => {
    expect(isSetupComplete(parseSetupProgress(null), true)).toBe(true);
  });

  it('migrates saved answers from the previous setup flow', () => {
    expect(resumeSetupQuestion(parseSetupProgress('readiness reviewer delivery'))).toBe(6);
  });
});
