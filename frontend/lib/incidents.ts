import type { ApprovalGate, Incident, IncidentAction, IncidentActionKind, IncidentState } from '@hackatl/frontend-transport';

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
