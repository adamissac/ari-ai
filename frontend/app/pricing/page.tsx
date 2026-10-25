import type { Metadata } from 'next';
import Link from 'next/link';
import { BRAND_NAME } from '@/components/brand';
import { Faq } from '@/components/faq';
import { DEMO_ONLY } from '@/lib/deployment';
import { perAssessment, PLANS, usd } from '@/lib/pricing';

const START = DEMO_ONLY ? '/access' : '/projects';

export const metadata: Metadata = {
  title: `Pricing · ${BRAND_NAME}`,
  description: `${BRAND_NAME} plans: Founder, Growth, Scale and Enterprise, priced by full assessments and assessed source lines per month.`,
};

/* Proposed plans for after the pilot; nothing can be purchased. */
const INCLUDED = [
  'Intent-aware review of every pull request against what the code is meant to do',
  'A failing test generated to reproduce each functional defect it reports',
  'Seven security agents probing only inside the sandbox scope you approve',
  'Fixes proposed only after human approval, and closed only when independent tests pass',
  'Signed GitHub monitoring that re-checks every push for regressions',
  'Evidence for every claim: source spans, test reports and agent transcripts',
];

const ENTERPRISE_ADDS = [
  'Custom assessment and source-line volumes',
  'SARIF and rules-of-engagement reports for every assessment',
  'Findings mapped to CWE, CVSS, OWASP LLM Top 10, MITRE ATT&CK and D3FEND',
  'Scope and rules of engagement agreed in writing before any testing',
  'Two-person approval for containment and incident closure workflows',
  'A persisted audit trail of every approval and decision',
];

const FAQ = [
  { q: 'What is a full assessment?', a: 'One run on one commit: intent review, the seven security agents inside your approved scope, and independent verification of any fix.' },
  { q: 'What counts as assessed source lines?', a: 'In this proposal, the source lines ARI reads across all full assessments in a month. Assessing a 50,000-line repository three times counts as 150,000 lines.' },
  { q: 'Does ARI ever change our code on its own?', a: 'No. Patches are proposed only after a person approves remediation, and a fix only counts when independent, executed tests agree.' },
  { q: 'What will ARI test?', a: 'Only the scope you approve, such as sandbox builds of your own repositories. It never targets third-party systems.' },
  { q: 'Is the Defense Lab live network defense?', a: 'No. It is a policy trained and evaluated in an isolated test network, shown as decision support. Nothing it recommends is applied automatically.' },
  { q: 'Can I buy a plan today?', a: 'Not yet. This is a hackathon preview: the plans above are proposals and nothing can be purchased. You can open the console and try the product.' },
];

export default function PricingPage() {
  return (
    <div className="mk">
      <header className="hero-full mk-hero pb-20 pt-24" aria-labelledby="pricing-title">
        <div className="mk-wrap">
          <p className="mk-kicker"><b>Pricing</b> · private pilot</p>
          <h1 id="pricing-title" className="mk-display mt-6">Pilot first.<br /><span className="dim">Plans later.</span></h1>
          <p className="mk-lede mt-6">{BRAND_NAME} is in a private pilot. You start each review yourself and approve every fix. The plans below are proposals for after the pilot.</p>
          <p className="mk-kicker mt-4" data-testid="pricing-proposal">Hackathon preview: plans are proposals, nothing can be purchased.</p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href={START} className="mk-btn mk-btn-primary">Open the console<span aria-hidden="true" className="arrow">→</span></Link>
            <Link href="/#how" className="mk-btn mk-btn-secondary">How it works</Link>
          </div>
        </div>
      </header>

      <div className="hero-cover">
        <section aria-label="Plans" className="mk-section">
          <div className="mk-wrap">
            <p className="mk-list-title">Proposed plans · USD per month</p>
            <div className="mk-plans" role="table" aria-label="Proposed plans">
              <div className="mk-plan mk-plan-head" role="row">
                <span role="columnheader">Plan</span><span role="columnheader">Proposed price</span><span role="columnheader">Full assessments</span><span role="columnheader">Assessed lines</span><span role="columnheader">Per assessment</span>
              </div>
              {PLANS.map(plan => (
                <div key={plan.id} className="mk-plan" role="row" data-testid={`plan-${plan.id}`} data-recommended={plan.recommended || undefined}>
                  <span role="cell"><b>{plan.name}</b><small>{plan.tagline}</small></span>
                  <span role="cell" className="mk-plan-price">{plan.monthlyUsd === null ? 'Contact us' : usd(plan.monthlyUsd)}</span>
                  <span role="cell"><i>Full assessments </i>{plan.assessments ?? 'Custom'}</span>
                  <span role="cell"><i>Assessed lines </i>{plan.sourceLines}</span>
                  <span role="cell"><i>Per assessment </i>{perAssessment(plan)}</span>
                </div>
              ))}
            </div>
            <p className="mt-4 text-xs text-faint" data-testid="pricing-preview">Hackathon preview: these plans are proposals and nothing can be purchased yet. Prices in USD.</p>

            <div className="mk-grid2">
              <div>
                <p className="mk-list-title">Every plan would include</p>
                <ul className="mk-bullets">{INCLUDED.map(f => <li key={f}>{f}</li>)}</ul>
              </div>
              <div>
                <p className="mk-list-title">Enterprise would add</p>
                <ul className="mk-bullets">{ENTERPRISE_ADDS.map(f => <li key={f}>{f}</li>)}</ul>
              </div>
            </div>
          </div>
        </section>

        <section aria-labelledby="faq-title" className="mk-section mk-paper">
          <div className="mk-wrap grid items-start gap-10 md:grid-cols-12 md:gap-6">
            <div className="md:col-span-4">
              <p className="mk-kicker">FAQ</p>
              <h2 id="faq-title" className="mk-h2 mt-4">Questions, answered</h2>
              <p className="mk-lede mt-4 text-sm">How plans would work, and what {BRAND_NAME} will and won’t do to your code.</p>
            </div>
            <div className="md:col-span-8"><Faq items={FAQ} /></div>
          </div>
        </section>
      </div>
    </div>
  );
}
