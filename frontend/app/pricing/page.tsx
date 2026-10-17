import type { Metadata } from 'next';
import Link from 'next/link';
import { BRAND_NAME } from '@/components/brand';
import { RollText } from '@/components/ui';

export const metadata: Metadata = {
  title: `Pricing · ${BRAND_NAME}`,
  description: `${BRAND_NAME} plans: assurance on every pull request, or continuous assessment for organizations at scale.`,
};

/* Preview pricing: the layout follows kairo.security's pricing page; plan contents describe
   what Ari AI does. Price points are a placeholder for the owner to confirm. */
const TEAM = {
  name: 'Team',
  tagline: 'Assurance on every pull request',
  price: '$40',
  unit: '/ seat / month',
  cta: 'Start 14-day free trial',
  heading: 'What’s included',
  features: [
    'Intent-aware review of every pull request against what the code is meant to do',
    'A failing test generated to reproduce each functional defect it reports',
    'Seven security agents probing only inside the sandbox scope you approve',
    'Fixes proposed only after human approval, and closed only when independent tests pass',
    'Signed GitHub monitoring that re-checks every push for regressions',
    'Unlimited repositories and every developer’s pull requests',
    'Evidence for every claim: source spans, test reports and agent transcripts',
    '14-day free trial',
  ],
};

const ENTERPRISE = {
  name: 'Enterprise',
  tagline: 'Best for organizations at scale',
  price: 'Custom pricing',
  cta: 'Contact sales',
  heading: 'Everything in Team, plus',
  features: [
    'Continuous re-assessment on every change, not a point-in-time test',
    'SARIF and rules-of-engagement reports for every assessment',
    'Findings mapped to CWE, CVSS, OWASP LLM Top 10, MITRE ATT&CK and D3FEND',
    'Scope and rules of engagement agreed in writing before any testing',
    'Defense Lab decision support, trained in simulation and never applied automatically',
    'Two-person approval for containment and incident closure workflows',
    'SSO, audit logging and per-tenant isolation',
    'A named security engineer and a quarterly programme review',
    'Annual terms and invoiced billing',
  ],
};

const FAQ = [
  { q: 'What counts as a seat?', a: 'A developer whose pull requests Ari AI reviews in a billing month. Reviewers, approvers and read-only viewers are free.' },
  { q: 'What is an assessment?', a: 'One run on one commit: intent review, the seven security agents inside your approved scope, and independent verification of any fix.' },
  { q: 'Does Ari AI ever change our code on its own?', a: 'No. Patches are proposed only after a person approves remediation, and a fix only counts when independent, executed tests agree.' },
  { q: 'What will Ari AI test?', a: 'Only the scope you approve, such as sandbox builds of your own repositories. It never targets third-party systems.' },
  { q: 'Is the Defense Lab live network defense?', a: 'No. It is a policy trained and evaluated in simulation, shown as decision support. Nothing it recommends is applied automatically.' },
  { q: 'Can I cancel?', a: 'Yes, at any time. Your plan stays active until the end of the billing period.' },
];

function Check({ dark }: { dark?: boolean }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 16 16" className={`mt-0.5 h-4 w-4 shrink-0 ${dark ? 'text-white/70' : 'text-brand'}`}>
      <path d="M3.5 8.5l3 3 6-7" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function Cta({ href, children, tone }: { href: string; children: string; tone: 'light' | 'dark' }) {
  return (
    <Link href={href} className={`group label-mono inline-flex h-10 items-center rounded-md px-4 transition-colors duration-[250ms] ${tone === 'light' ? 'bg-white text-ink hover:bg-brand hover:text-on-brand' : 'bg-ink text-white hover:bg-brand'}`}>
      <RollText>{children}</RollText>
    </Link>
  );
}

export default function PricingPage() {
  return (
    <div className="pricing">
      <header className="hero-ink bleed-hero -mt-6 px-6 pb-20 pt-16 md:px-12 md:pb-28 md:pt-24" aria-labelledby="pricing-title">
        <div className="mx-auto max-w-7xl">
          <p className="pricing-pill label-mono"><span aria-hidden="true" className="hero-ping" />Pricing</p>
          <h1 id="pricing-title" className="display mt-5 text-5xl font-semibold md:text-7xl">{BRAND_NAME} pricing</h1>
          <p className="mt-4 max-w-xl text-sm text-white/70 md:text-base">Know what every change does, prove every fix, and keep checking as your code moves.</p>
          <div className="mt-7"><Cta href="/projects" tone="light">Start 14-day free trial</Cta></div>
        </div>
      </header>

      <section aria-label="Plans" className="pricing-plans -mt-12 grid gap-4 md:-mt-16 lg:grid-cols-2">
        <article className="pricing-card pricing-card-dark" aria-labelledby="plan-team">
          <div className="flex items-start justify-between gap-3">
            <h2 id="plan-team" className="text-2xl font-semibold">{TEAM.name}</h2>
            <span className="pricing-badge label-mono">Recommended</span>
          </div>
          <p className="mt-2 text-sm text-white/70">{TEAM.tagline}</p>
          <p className="mt-8 flex items-baseline gap-2">
            <span className="font-display text-6xl font-semibold tracking-tight">{TEAM.price}</span>
            <span className="label-mono text-white/60">{TEAM.unit}</span>
          </p>
          <div className="mt-6"><Cta href="/projects" tone="light">{TEAM.cta}</Cta></div>
          <hr className="my-8 border-white/10" />
          <p className="label-mono text-white/60">{TEAM.heading}</p>
          <ul className="mt-4 flex flex-col gap-3 text-sm text-white/85">
            {TEAM.features.map(f => <li key={f} className="flex gap-3"><Check dark />{f}</li>)}
          </ul>
        </article>

        <article className="pricing-card pricing-card-light" aria-labelledby="plan-enterprise">
          <h2 id="plan-enterprise" className="text-2xl font-semibold">{ENTERPRISE.name}</h2>
          <p className="mt-2 text-sm text-muted">{ENTERPRISE.tagline}</p>
          <p className="mt-8 font-display text-5xl font-semibold tracking-tight md:text-6xl">{ENTERPRISE.price}</p>
          <div className="mt-6"><Cta href="/projects" tone="dark">{ENTERPRISE.cta}</Cta></div>
          <hr className="my-8 border-line" />
          <p className="label-mono text-faint">{ENTERPRISE.heading}</p>
          <ul className="mt-4 flex flex-col gap-3 text-sm text-ink">
            {ENTERPRISE.features.map(f => <li key={f} className="flex gap-3"><Check />{f}</li>)}
          </ul>
        </article>
      </section>
      <p className="mt-4 text-center text-xs text-faint" data-testid="pricing-preview">Preview pricing, subject to change. Prices are in USD and exclude tax.</p>

      <section aria-labelledby="faq-title" className="mt-24 grid gap-8 md:grid-cols-[1fr_3fr]">
        <h2 id="faq-title" className="label-mono flex items-start gap-2 text-faint"><span aria-hidden="true" className="mt-1 inline-block h-1.5 w-1.5 rounded-full bg-brand" />FAQ</h2>
        <div className="pricing-faq">
          {FAQ.map(item => (
            <details key={item.q} className="pricing-faq-item group">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-5 text-base font-medium md:text-lg">
                {item.q}
                <span aria-hidden="true" className="pricing-faq-icon">+</span>
              </summary>
              <p className="max-w-2xl pb-5 text-sm text-muted">{item.a}</p>
            </details>
          ))}
        </div>
      </section>

      <section aria-labelledby="pricing-cta" className="hero-ink mb-16 mt-24 rounded-2xl px-6 py-14 text-center md:px-12 md:py-20">
        <h2 id="pricing-cta" className="display mx-auto max-w-3xl text-3xl font-semibold md:text-5xl">See what your code really does before an attacker does.</h2>
        <div className="mt-8 flex flex-wrap justify-center gap-2">
          <Cta href="/projects" tone="light">Get started</Cta>
          <Link href="/#how" className="group label-mono inline-flex h-10 items-center rounded-md bg-white/10 px-4 text-white transition-colors duration-[250ms] hover:bg-white/20">
            <RollText>See how it works</RollText>
          </Link>
        </div>
      </section>
    </div>
  );
}
