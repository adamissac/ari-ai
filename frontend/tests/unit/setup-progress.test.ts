import { describe, expect, it } from 'vitest';
import { answerSetupQuestion, canVisitSetupQuestion, initialSetupProgress, isSetupComplete, parseSetupProgress, progressFromServer, progressToServer, resumeSetupQuestion, setupProgressKey } from '@/lib/setup-progress';

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

  it('round-trips progress through the server shape', () => {
    const progress = { answers: { readiness: true, strictness: '2', comments: false }, complete: false };
    const wire = progressToServer(progress);
    expect(wire.answers.watch).toBeNull();
    expect(wire.answers.comments).toBe(false);
    expect(progressFromServer({ repo_id: 'r', ...wire, completed_at: null, updated_at: null })).toEqual(progress);
  });

  it('prefers the server copy and migrates browser progress only when the server is empty', () => {
    const empty = { answers: {}, complete: false };
    const legacy = { answers: { readiness: true }, complete: true };
    expect(initialSetupProgress(empty, legacy)).toEqual({ progress: legacy, migrate: true });
    expect(initialSetupProgress(empty, null)).toEqual({ progress: empty, migrate: false });
    const server = { answers: { readiness: true, strictness: '1' }, complete: false };
    expect(initialSetupProgress(server, legacy)).toEqual({ progress: server, migrate: false });
  });
});
