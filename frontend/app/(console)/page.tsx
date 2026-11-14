'use client';

import { LandingFooter } from '@/components/landing-footer';

import Link from 'next/link';
import { BRAND_HEADLINE, BRAND_HEADLINE_REST } from '@/components/brand';
import { HeroStage } from '@/components/hero';
import { HeroAnts } from '@/components/hero-ants';
import { ProductPreview } from '@/components/product-preview';
import { HowItWorks, ProblemScene, ProofStats, Walkthrough } from '@/components/story';
import { OptionalUserBar } from '@/components/user-bar';
import { DEMO_ONLY } from '@/lib/deployment';

// A demo-only build has no backend, so the calls to action open the access-code sign-in.
const START = DEMO_ONLY ? { href: '/access', hero: 'Sign in' } : { href: '/projects', hero: 'Go to projects' };

export default function HomePage() {
  return (
    <div className="home-deep marketing-atmosphere">
      <HeroStage className="hero-full px-6 pb-20 pt-32 md:px-12 md:pt-36" labelledBy="hero-title" base={<HeroAnts />}>
        <div className="hero-split mx-auto w-full max-w-6xl">
          <div>
            <h1 id="hero-title"><span className="block">{BRAND_HEADLINE}</span>{' '}<span className="block hero-accent">{BRAND_HEADLINE_REST}</span></h1>
            <p className="hero-sub">Ari reviews every commit against what the code is meant to do, attacks it in a sandbox, and commits the fix only after independent tests prove it.</p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href={START.href} className="btn-primary">{START.hero}</Link>
              <a href="#how" className="btn-quiet">How it works</a>
            </div>
            <dl className="hero-facts">
              <div><dt>Commits reviewed in the pilot</dt><dd>1,205</dd></div>
              <div><dt>Planted flaws fixed and verified</dt><dd>All, across 3 test apps</dd></div>
              <div><dt>Fixes merged without a passing test</dt><dd>0</dd></div>
            </dl>
          </div>
          <ProductPreview />
        </div>
      </HeroStage>

      <div className="hero-cover -mb-6 pt-6">
        {!DEMO_ONLY && <OptionalUserBar />}

        <ProblemScene />
        <HowItWorks />
        <Walkthrough />
        <ProofStats />
        <LandingFooter />


      </div>
    </div>
  );
}
