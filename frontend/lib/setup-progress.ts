export const SETUP_QUESTIONS = [
  'readiness',
  'strictness',
  'reviewChanges',
  'comments',
  'watch',
  'scope',
  'delivery',
  'reviewStart',
] as const;

export type SetupQuestion = typeof SETUP_QUESTIONS[number];
export type SetupProgress = {
  answers: Partial<Record<SetupQuestion, string | boolean>>;
  complete: boolean;
};

export function setupProgressKey(projectId: string, repoId: string) {
  return `ari-setup:${projectId}:${repoId}`;
}

export function parseSetupProgress(raw: string | null): SetupProgress {
  if (!raw) return { answers: {}, complete: false };
  try {
    const value = JSON.parse(raw) as Partial<SetupProgress>;
    if (!value || typeof value !== 'object' || !value.answers || typeof value.answers !== 'object') {
      return { answers: {}, complete: false };
    }
    const answers: SetupProgress['answers'] = {};
    for (const question of SETUP_QUESTIONS) {
      const answer = value.answers[question];
      if (typeof answer === 'string' || typeof answer === 'boolean') answers[question] = answer;
    }
    return { answers, complete: value.complete === true };
  } catch {
    const legacy = new Set(raw.split(/\s+/).filter(Boolean));
    const answers: SetupProgress['answers'] = {};
    if (legacy.has('readiness')) answers.readiness = true;
    if (legacy.has('reviewer')) {
      answers.strictness = true;
      answers.reviewChanges = true;
      answers.comments = true;
      answers.watch = true;
    }
    if (legacy.has('delivery')) answers.delivery = true;
    return { answers, complete: false };
  }
}

export function answerSetupQuestion(progress: SetupProgress, question: SetupQuestion, answer: string | boolean): SetupProgress {
  return { ...progress, answers: { ...progress.answers, [question]: answer } };
}

export function resumeSetupQuestion(progress: SetupProgress): number {
  return SETUP_QUESTIONS.findIndex(question => progress.answers[question] === undefined) + 1 || SETUP_QUESTIONS.length;
}

export function canVisitSetupQuestion(progress: SetupProgress, questionNumber: number): boolean {
  return Number.isInteger(questionNumber) && questionNumber >= 1 && questionNumber <= resumeSetupQuestion(progress);
}

export function isSetupComplete(progress: SetupProgress, hasAssessment: boolean): boolean {
  return progress.complete || hasAssessment;
}
