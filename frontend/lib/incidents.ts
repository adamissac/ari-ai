import type { ApprovalGate, EvidenceRef, Incident, IncidentAction, IncidentActionKind, IncidentState, PatchView } from '@hackatl/frontend-transport';

/** Mirror of standards.incident.INCIDENT_TRANSITIONS; the backend remains the authority. */
export const NEXT_STATES: Record<IncidentState, IncidentState[]> = {
  reported: ['rejected'],
  triaged: ['analysis', 'rejected'],
  analysis: ['containment'],
  containment: ['eradication'],
  eradication: ['recovery'],
  recovery: ['closed'],
  closed: [],
  rejected: [],
};

/** Gated target state → the approval gate it needs, requested from the preceding state. */
export const GATE_FOR: Partial<Record<IncidentState, ApprovalGate>> = {
  containment: 'containment',
  eradication: 'eradication',
  recovery: 'recovery',
  closed: 'closure',
};

export const STATE_LABEL: Record<IncidentState, string> = {
  reported: 'Reported', triaged: 'Triaged', analysis: 'Analysis', containment: 'Containment',
  eradication: 'Eradication', recovery: 'Recovery', closed: 'Closed', rejected: 'Rejected',
};

export const LIFECYCLE: IncidentState[] = ['reported', 'triaged', 'analysis', 'containment', 'eradication', 'recovery', 'closed'];

/** Generated DTOs require every key; unspecified action fields are explicit nulls/empties. */
export function action(kind: IncidentActionKind, fields: Partial<IncidentAction> = {}): IncidentAction {
  return {
    kind, note: '', target_state: null, triage_decision: null, category: null, business_priority: null,
    owner: null, gate: null, approve: null, action_summary: null, finding_ids: [], monitoring_event_ids: [],
    recommendation_ids: [], verification_ids: [], audience: null, channel: null, csf_ref: null,
    criterion_key: null, evidence: [], ...fields,
  };
}

export function approvalFor(incident: Incident, gate: ApprovalGate) {
  return [...incident.approvals].reverse().find(a => a.gate === gate);
}

/** An evidence reference the user can attach, with where it came from. */
export interface EvidenceOption { key: string; label: string; ref: EvidenceRef; regression: boolean }

function artifactRef(artifactId: string, sha256: string, provenance: string, note: string): EvidenceRef {
  return { kind: 'artifact', path: null, commit_sha: null, span: null, symbol: null, artifact_id: artifactId, sha256, provenance, note };
}

/**
 * Patch diffs for a linked finding. The backend checks evidence against the *stored* artifact hash,
 * which differs from `diff_sha256` when the artifact store redacted the diff, so cite the stored hash.
 */
export function patchEvidence(findingId: string, views: PatchView[], storedSha: Record<string, string>): EvidenceOption[] {
  return views.flatMap(({ patch, verification }) => {
    const sha = storedSha[patch.diff_artifact_id];
    if (!sha) return [];
    const redacted = sha !== patch.diff_sha256 ? ' · stored copy redacted' : '';
    return [{
      key: patch.diff_artifact_id,
      label: `Patch #${patch.attempt} diff · ${findingId}${verification ? ` · Verify ${verification.verdict}` : ''}${redacted}`,
      ref: artifactRef(patch.diff_artifact_id, sha, 'agent:patch', `patch ${patch.id} for ${findingId}`),
      regression: false,
    }];
  });
}

/** A Fortify-proposed regression test artifact; the only evidence accepted for lessons learned. */
export function regressionEvidence(findingId: string, artifactId: string, sha256: string): EvidenceOption {
  return {
    key: artifactId,
    label: `Fortify regression test · ${findingId}`,
    ref: artifactRef(artifactId, sha256, 'agent:fortify', `regression test for ${findingId}`),
    regression: true,
  };
}

export function acceptedVerifications(views: PatchView[]): string[] {
  return views.flatMap(v => (v.verification?.verdict === 'accepted' ? [v.verification.id] : []));
}

/** What still stands between the incident and closure (backend remains the authority). */
export function closureBlockers(incident: Incident): string[] {
  const out: string[] = [];
  if (incident.state === 'closed' || incident.state === 'rejected') return out;
  if (incident.closure_criteria.length === 0) out.push('Add at least one closure criterion.');
  const open = incident.closure_criteria.filter(c => !c.satisfied).map(c => c.key);
  if (open.length > 0) out.push(`Satisfy with evidence: ${open.join(', ')}.`);
  if (!incident.lessons_learned || incident.lessons_learned_evidence.length === 0) out.push('Record lessons learned with Fortify regression-test evidence.');
  if (approvalFor(incident, 'closure')?.status !== 'approved') out.push('A second member must approve the closure gate (requested from Recovery).');
  return out;
}
