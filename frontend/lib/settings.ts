import type { Budget, DeliveryMode, Project, ProjectSettings } from '@hackatl/frontend-transport';

export interface Draft {
  name: string; languages: string;
  maxTokens: string; maxUsd: string; maxWall: string;
  enabled: boolean; interval: string; ignore: string;
  monTokens: string; monUsd: string; monWall: string;
  deliveryMode: DeliveryMode;
}

export function draftOf(p: Project): Draft {
  const s = p.settings;
  const m = s.monitoring_policy;
  return {
    name: p.name,
    languages: s.languages.join(', '),
    maxTokens: String(s.default_budget.max_tokens),
    maxUsd: String(s.default_budget.max_usd),
    maxWall: String(s.default_budget.max_wall_clock_s),
    enabled: m.enabled,
    interval: String(m.min_interval_s),
    ignore: m.ignore_paths_only.join('\n'),
    monTokens: String(m.monitoring_budget.max_tokens),
    monUsd: String(m.monitoring_budget.max_usd),
    monWall: String(m.monitoring_budget.max_wall_clock_s),
    deliveryMode: s.delivery_mode,
  };
}

const int = (v: string, min: number): number | null => (/^\d+$/.test(v.trim()) && Number(v) >= min ? Number(v) : null);
const usd = (v: string): number | null => (/^\d+(\.\d+)?$/.test(v.trim()) ? Number(v) : null);
const split = (text: string, sep: RegExp): string[] => text.split(sep).map(x => x.trim()).filter(Boolean);

function budget(label: string, tokens: string, dollars: string, wall: string): Budget | string {
  const max_tokens = int(tokens, 0);
  const max_usd = usd(dollars);
  const max_wall_clock_s = int(wall, 1);
  if (max_tokens === null) return `${label}: max tokens must be a whole number ≥ 0.`;
  if (max_usd === null) return `${label}: max USD must be a number ≥ 0.`;
  if (max_wall_clock_s === null) return `${label}: wall clock must be a whole number of seconds ≥ 1.`;
  return { max_tokens, max_usd, max_wall_clock_s };
}

/** Validates the form into a whole ProjectSettings object (the backend re-validates). */
export function parseSettings(d: Draft): { settings: ProjectSettings } | { error: string } {
  if (!d.name.trim()) return { error: 'Project name is required.' };
  const languages = split(d.languages, /,/);
  if (languages.length === 0) return { error: 'At least one language is required.' };
  const def = budget('Default budget', d.maxTokens, d.maxUsd, d.maxWall);
  if (typeof def === 'string') return { error: def };
  const mon = budget('Monitoring budget', d.monTokens, d.monUsd, d.monWall);
  if (typeof mon === 'string') return { error: mon };
  const interval = int(d.interval, 0);
  if (interval === null) return { error: 'Minimum interval must be a whole number of seconds ≥ 0.' };
  return {
    settings: {
      default_budget: def,
      monitoring_policy: { enabled: d.enabled, min_interval_s: interval, ignore_paths_only: split(d.ignore, /\n/), monitoring_budget: mon },
      languages,
      delivery_mode: d.deliveryMode,
      delivery_authorized_by: null, // the server records who enabled auto delivery
    },
  };
}

export const AUTO_WARNING =
  'Ari will commit verified fixes straight to your default branch with no human review (it opens a pull request instead if the branch moved or is protected). Continue?';
