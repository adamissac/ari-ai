import type { CheckCategory } from '@hackatl/frontend-transport';

/** Canonical Probe library ids offered when requesting a scope (SEC-005). */
export const SCOPE_CHECK_CATEGORIES: readonly CheckCategory[] = [
  'access_control.ownership',
  'input_validation.bounds',
];
