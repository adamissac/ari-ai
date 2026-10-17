import type { AssessmentState } from '@hackatl/frontend-transport';
import { ASSESSMENT_STATE } from '@/lib/status';

/** One sentence for the assessment's recorded state. It does not infer phases the run has not entered. */
export function currentPhaseSentence(state: AssessmentState): string {
  switch (state) {
    case 'FAILED':
      return 'This check failed. The recorded error is on this page. This is not a clean result.';
    case 'CANCELLED':
      return 'This check was cancelled.';
    case 'BUDGET_EXHAUSTED':
      return 'This check ran out of budget. That is not a clean result.';
    case 'AWAITING_APPROVAL':
      return 'This check is paused until a person approves a candidate fix. Nothing is merged or deployed.';
    case 'COMPLETED':
      return 'This check finished. A finished check is not a claim that the whole application is secure.';
    case 'CREATED':
      return 'This check has been created. No later phase is recorded yet.';
    default:
      return `This check is in ${ASSESSMENT_STATE[state].label}.`;
  }
}
