/** Proposed plans (hackathon preview; nothing can be purchased). Shown on /pricing. */
export interface Plan {
  id: string;
  name: string;
  tagline: string;
  monthlyUsd: number | null; // null = contact us
  assessments: number | null;
  sourceLines: string;
  recommended?: boolean;
}

export const PLANS: readonly Plan[] = [
  { id: 'founder', name: 'Founder', tagline: 'For a founder shipping a first product', monthlyUsd: 49.99, assessments: 7, sourceLines: '1 million' },
  { id: 'growth', name: 'Growth', tagline: 'For a team shipping every week', monthlyUsd: 129.99, assessments: 20, sourceLines: '5 million', recommended: true },
  { id: 'scale', name: 'Scale', tagline: 'For several teams and services', monthlyUsd: 359.99, assessments: 60, sourceLines: '20 million' },
  { id: 'enterprise', name: 'Enterprise', tagline: 'Best for organizations at scale', monthlyUsd: null, assessments: null, sourceLines: 'Custom' },
];

export const usd = (x: number) => `$${x.toFixed(2)}`;
/** Monthly price divided by included assessments, to the cent. */
export const perAssessment = (p: Plan): string =>
  p.monthlyUsd === null || !p.assessments ? 'Custom' : usd(Math.round((p.monthlyUsd / p.assessments) * 100) / 100);
