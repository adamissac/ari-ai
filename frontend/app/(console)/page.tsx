'use client';

import { LandingFooter } from '@/components/landing-footer';

import Link from 'next/link';
import { BRAND_HEADLINE, BRAND_HEADLINE_REST } from '@/components/brand';
import { HeroStage } from '@/components/hero';
import { ProductPreview } from '@/components/product-preview';
import { HowItWorks, ProblemScene, ProofStats, Walkthrough } from '@/components/story';
import { OptionalUserBar } from '@/components/user-bar';
import { DEMO_ONLY } from '@/lib/deployment';

// A demo-only build has no backend, so the calls to action open the access-code sign-in.
const START = DEMO_ONLY ? { href: '/access', hero: 'Sign in' } : { href: '/projects', hero: 'Go to projects' };

export default function HomePage() {
  return (
    <div className="home-deep marketing-atmosphere">
      <HeroStage className="hero-full px-6 pb-20 pt-32 md:px-12 md:pt-36" labelledBy="hero-title">
        <div className="hero-split mx-auto w-full max-w-6xl">
          <div>
            <h1 id="hero-title">{BRAND_HEADLINE}<br />{BRAND_HEADLINE_REST}</h1>
            <p className="hero-sub">Ari reviews every commit, tries to break it in a sandbox, and opens a fix only after independent tests pass.</p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href={START.href} className="btn-primary">{START.hero}</Link>
              <a href="#how" className="btn-quiet">How it works</a>
            </div>
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
