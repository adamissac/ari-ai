/** Result of a simulated attack drill (backend `attack_drill` job), validated before display. */
export interface DrillResult {
  repo: string;
  planAuthor: 'claude' | 'scripted';
  plan: { route: string; technique: string; attacker: string; objective: string; narrative: string; steps: string[] };
  detection: { detected: boolean; anomalyScore: number; reasons: string[]; eventIds: string[]; linkedFindings: string[] };
  response: { responder: string; executed: false; actions: { action: string; detail: string }[] };
}

const str = (v: unknown): v is string => typeof v === 'string';
const strs = (v: unknown): v is string[] => Array.isArray(v) && v.every(str);
const rec = (v: unknown): Record<string, unknown> | null => (v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : null);

export const TECHNIQUE_LABEL: Record<string, string> = {
  enumeration: 'ID enumeration',
  credential_stuffing: 'Credential stuffing',
  bounds_abuse: 'Limit abuse',
};

/** Null when the job result is not a well-formed, simulated drill result. */
export function parseDrillResult(raw: unknown): DrillResult | null {
  const r = rec(raw), plan = rec(r?.plan), det = rec(r?.detection), resp = rec(r?.response);
  if (!r || !plan || !det || !resp || r.simulated !== true || !str(r.repo)) return null;
  if (r.plan_author !== 'claude' && r.plan_author !== 'scripted') return null;
  if (![plan.route, plan.technique, plan.attacker, plan.objective, plan.narrative].every(str) || !strs(plan.steps)) return null;
  if (typeof det.detected !== 'boolean' || typeof det.anomaly_score !== 'number' || !strs(det.reasons) || !strs(det.monitoring_event_ids) || !strs(det.linked_findings)) return null;
  if (resp.executed !== false || !str(resp.responder) || !Array.isArray(resp.actions)) return null;
  const actions = resp.actions.map(rec);
  if (actions.some(a => !a || !str(a.action) || !str(a.detail))) return null;
  return {
    repo: r.repo,
    planAuthor: r.plan_author,
    plan: { route: plan.route as string, technique: plan.technique as string, attacker: plan.attacker as string, objective: plan.objective as string, narrative: plan.narrative as string, steps: plan.steps },
    detection: { detected: det.detected, anomalyScore: det.anomaly_score, reasons: det.reasons, eventIds: det.monitoring_event_ids, linkedFindings: det.linked_findings },
    response: { responder: resp.responder, executed: false, actions: actions.map(a => ({ action: a!.action as string, detail: a!.detail as string })) },
  };
}
