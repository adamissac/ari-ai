/** Plain-language definitions for terms the UI cannot avoid. Explanations, not results. */
export const GLOSSARY = {
  finding: 'Something the checks noticed that may be wrong with the code. It starts as a suspicion and only counts as real once a test confirms it.',
  hypothesis: 'A suspicion that has not been tested yet. It may turn out to be wrong.',
  validated: 'A test reproduced the problem, so it is real.',
  scope: 'A written permission that says exactly which copy of the software the agents may test, and which kinds of tests they may run. Another person has to approve it.',
  sandbox: 'A sealed-off copy of the software, built only for testing, so nothing real can be harmed.',
  patch: 'A proposed change to the code that should fix the problem. It is a suggestion; it is not applied to the real software.',
  verification: 'An independent re-test of a proposed fix. The fix only counts when the original problem no longer reproduces and the normal tests still pass.',
  commit: 'One saved version of the code. Each commit has a long ID (its "SHA").',
  agent: 'An AI worker with one job and a limited set of tools. Each of the eight agents is a separate program.',
  approval: 'A decision a person makes before the system is allowed to do something with consequences.',
  monitoring: 'Watching the code repository for new changes, so each change can be checked again.',
  'live defense': 'The customer view of recorded events, incidents and simulation-trained recommendations for a project. It does not apply controls on a live system.',
  simulation: 'A practice environment made of fake computers. Results from it say nothing certain about real networks.',
  policy: 'The decision rule a defender follows: for each situation, which action to take.',
  provider: 'Where the AI replies came from. "Live" means a real AI model answered; "scripted" means pre-written test replies were used.',
} as const;

export type GlossaryTerm = keyof typeof GLOSSARY;
