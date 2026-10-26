'use client';

import { LandingFooter } from '@/components/landing-footer';

import Link from 'next/link';
import { useState, type CSSProperties } from 'react';
import { BRAND_HEADLINE, BRAND_HEADLINE_REST, BRAND_TAGLINE } from '@/components/brand';
import { HowItWorks, ProblemScene, ProofStats, Walkthrough } from '@/components/story';
import { ASSESSMENT_LOOP, HeroStage } from '@/components/hero';
import { IntroLoader } from '@/components/intro-loader';
import { OptionalUserBar } from '@/components/user-bar';
import { ExplainerVideo } from '@/components/explainer-video';
import { DEMO_ONLY } from '@/lib/deployment';
import { RollText } from '@/components/ui';
import { HeroExploit } from '@/components/hero-exploit';
import { HeroAnts } from '@/components/hero-ants';

const LOOP = ASSESSMENT_LOOP;

// A demo-only build has no backend, so the calls to action open the access-code sign-in.
const START = DEMO_ONLY ? { href: '/access', hero: 'Sign in' } : { href: '/projects', hero: 'Go to projects' };

const i = (n: number) => ({ '--i': n }) as CSSProperties;

export default function HomePage() {
  const [revealed, setRevealed] = useState(false);

  return (
    <div className="home-deep marketing-atmosphere">
      <IntroLoader onReveal={() => setRevealed(true)} />
      <HeroStage className="hero-full px-6 pb-14 pt-36 md:px-12 md:pt-28" labelledBy="hero-title" play={revealed}>
        <div className="hero-center mx-auto w-full max-w-6xl text-center">
          <p className="kicker kicker-dark hero-in mx-auto" style={i(0)}>Seven agents · one shared brain</p>
          <h1 id="hero-title" className="hero-headline display mt-6 font-bold hero-in" style={i(1)}>
            <span data-glow={BRAND_HEADLINE} className="hero-line">{BRAND_HEADLINE}</span>{' '}
            <span data-glow={BRAND_HEADLINE_REST} className="hero-line hero-line-dim">{BRAND_HEADLINE_REST}</span>
          </h1>
          <p className="hero-in mx-auto mt-5 max-w-lg text-base text-white/75" style={i(2)}>{BRAND_TAGLINE}</p>
          <div className="hero-in mt-8 flex flex-wrap justify-center gap-3" style={i(3)}>
            <Link href={START.href} className="group label-mono inline-flex h-11 items-center rounded-md bg-white px-4 text-night transition-colors duration-[250ms] hover:bg-brand hover:text-on-brand">
              <RollText>{START.hero}</RollText>
            </Link>
            <a href="#how" className="group label-mono inline-flex h-11 items-center rounded-md bg-white/10 px-4 text-white transition-colors duration-[250ms] hover:bg-white/20">
              <RollText>How It Works</RollText>
            </a>
          </div>
          <div className="hero-in mt-12 text-left" style={i(4)}><HeroExploit play={revealed} stages={LOOP} /></div>
            <HeroAnts />
        </div>
      </HeroStage>

      <div className="hero-cover -mb-6 pt-6">
        {!DEMO_ONLY && <OptionalUserBar />}

        <ExplainerVideo />
        <ProblemScene />
        <HowItWorks />
        <Walkthrough />
        <ProofStats />
        <LandingFooter />


      </div>
    </div>
  );
}
