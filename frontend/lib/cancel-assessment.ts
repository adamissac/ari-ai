/** What Cancel assessment does, matching POST /assessments/{id}/cancel. */
export const CANCEL_ASSESSMENT_NOTE =
  'Cancel stops a check that has not started yet. If work has already begun, it requests a stop and the current step may finish. It does not delete findings or undo work already recorded.';

/** Copy for the cancel API's `cancelled` flag (immediate vs stop requested). */
export function cancelAssessmentResult(cancelled: boolean): string {
  return cancelled
    ? 'Cancelled before any worker started.'
    : 'Stop requested. The current step may finish before the check ends.';
}
