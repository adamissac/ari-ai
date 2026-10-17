const NEXT: Record<string, string> = {
  hypothesis: 'Probe has not confirmed this yet.',
  validated: 'A person can approve a candidate fix. Nothing is changed until then.',
  diagnosed: 'A remediation plan is recorded. A person still has to approve a candidate fix.',
  patch_proposed: 'Review the candidate patch. It has not been independently accepted.',
  verified: 'Independent tests accepted the candidate. It has not been merged or deployed.',
  patch_rejected: 'Verify did not accept the patch.',
  unresolved: 'The check did not produce an accepted fix.',
  hardened: 'A hardening note was recorded after verification.',
  accepted_risk: 'An owner recorded a decision to leave this unfixed.',
  closed: 'This finding is closed.',
  refuted: 'The check did not confirm the issue.',
  inconclusive: 'The check was inconclusive.',
  needs_recheck: 'A later change may have made this result stale.',
};

export interface StoryInput {
  title: string;
  status: string;
  severityRationale: string | null;
  validationOutcome: 'confirmed' | 'refuted' | 'inconclusive' | null;
  patchRationale: string | null;
  verification: 'accepted' | 'rejected' | null;
}

export function findingStory(input: StoryInput): { label: string; text: string }[] {
  const how = input.validationOutcome === 'confirmed'
    ? 'An approved test reproduced the issue.'
    : input.validationOutcome === 'refuted'
      ? 'An approved test did not reproduce the issue.'
      : input.validationOutcome === 'inconclusive'
        ? 'An approved test was inconclusive.'
        : 'No validation result was recorded.';
  const worked = input.verification === 'accepted'
    ? 'Independent tests accepted the candidate fix.'
    : input.verification === 'rejected'
      ? 'Independent tests rejected the candidate fix.'
      : 'Independent verification has not recorded a verdict.';
  return [
    { label: 'The problem', text: input.title },
    { label: 'Why it matters', text: input.severityRationale ?? 'No impact statement was recorded.' },
    { label: 'How we know', text: how },
    { label: 'What we changed', text: input.patchRationale ?? 'No candidate patch was recorded.' },
    { label: 'Did it work?', text: worked },
    { label: 'What happens next?', text: NEXT[input.status] ?? 'No next step is recorded for this status.' },
  ];
}

/** GitHub repo for source links. One project repo, or the assessment scope's only target. Never a guess among several. */
export function repoFullNameForEvidence(
  repos: readonly { id: string; full_name: string }[],
  scopeTargets: readonly { repo_id: string }[] | null,
): string | undefined {
  if (repos.length === 1) return repos[0]?.full_name;
  if (!scopeTargets) return undefined;
  const ids = [...new Set(scopeTargets.map(target => target.repo_id).filter(id => id.length > 0))];
  if (ids.length !== 1) return undefined;
  return repos.find(repo => repo.id === ids[0])?.full_name;
}
