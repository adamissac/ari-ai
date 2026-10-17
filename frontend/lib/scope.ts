import type { CheckCategory } from '@hackatl/frontend-transport';

/** Canonical Probe library ids offered when requesting a scope (SEC-005). */
export const SCOPE_CHECK_CATEGORIES: readonly CheckCategory[] = [
  'access_control.ownership',
  'input_validation.bounds',
];

/** What Request scope records: a pending authorization, not an active test window. */
export const REQUEST_SCOPE_NOTE =
  'Requesting a scope records a pending authorization for the listed sandbox build targets and check categories. It does not become active until a different project member approves it, and it does not start a check or grant access outside those targets.';
