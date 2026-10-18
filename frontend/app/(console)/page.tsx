'use client';

import Link from 'next/link';
import { useState, type CSSProperties } from 'react';
import { BRAND_HEADLINE, BRAND_HEADLINE_REST } from '@/components/brand';
import { Reveal } from '@/components/reveal';
import { HowItWorks, ProblemScene, ProofStats, Walkthrough } from '@/components/story';
import { ASSESSMENT_LOOP, HeroStage, useLoopCursor } from '@/components/hero';
import { IntroLoader } from '@/components/intro-loader';
import { OptionalUserBar } from '@/components/user-bar';
import { DEMO_ONLY } from '@/lib/deployment';
import { RollText } from '@/components/ui';

const LOOP = ASSESSMENT_LOOP;

// A demo-only build has no backend, so the calls to action open the access-code sign-in.
const START = DEMO_ONLY ? { href: '/access', hero: 'Sign in', end: 'Sign in' } : { href: '/projects', hero: 'Go to projects', end: 'Open projects' };

const i = (n: number) => ({ '--i': n }) as CSSProperties;

export default function HomePage() {
  const active = useLoopCursor(LOOP.length);
  const [revealed, setRevealed] = useState(false);

  return (
    <>
      <IntroLoader onReveal={() => setRevealed(true)} />
      <HeroStage className="hero-full px-6 pb-14 pt-44 md:px-12 md:pt-32" labelledBy="hero-title" play={revealed} colony>
        <div className="mx-auto w-full max-w-7xl text-center">
          <h1 id="hero-title" className="hero-headline display font-bold">
            <span data-spotlight className="hero-line hero-in" style={i(1)}>{BRAND_HEADLINE}</span><br />
            <span data-spotlight className="hero-line hero-line-dim hero-in text-white/70" style={i(2)}>{BRAND_HEADLINE_REST}</span>
          </h1>
          <div className="hero-in mt-10 flex flex-wrap justify-center gap-3" style={i(3)}>
            <Link href={START.href} className="group label-mono inline-flex h-11 items-center rounded-md bg-white px-4 text-ink transition-colors duration-[250ms] hover:bg-brand hover:text-on-brand">
              <RollText>{START.hero}</RollText>
            </Link>
            <a href="#how" className="group label-mono inline-flex h-11 items-center rounded-md bg-white/10 px-4 text-white backdrop-blur transition-colors duration-[250ms] hover:bg-white/20">
              <RollText>How It Works</RollText>
            </a>
          </div>
          <ol aria-label="Assessment loop" className="hero-in mx-auto mt-16 flex max-w-4xl flex-wrap justify-center gap-1.5" style={i(4)}>
            {LOOP.map((step, n) => (
              <li key={step} data-active={active === n || undefined} className="hero-step label-mono flex items-center gap-1.5 rounded-md bg-white/10 px-2.5 py-1 text-white/85 backdrop-blur transition-colors duration-[250ms] hover:bg-white/20">
                <span className="text-white/50">{String(n + 1).padStart(2, '0')}</span>{step}
              </li>
            ))}
          </ol>
        </div>
      </HeroStage>

      <div className="hero-cover -mb-6 pb-30 pt-6 md:pb-38">
        {!DEMO_ONLY && <OptionalUserBar />}

        <ProblemScene />
        <HowItWorks />
        <Walkthrough />
        <ProofStats />

        <Reveal className="mt-10">
          <section aria-labelledby="start-title" className="next-step">
            <div className="next-step-copy">
              <p className="label-mono next-step-eyebrow">✦ Your next move</p>
              <h2 id="start-title">From code change<br />to <span>clear evidence.</span></h2>
              <p>Bring a repository. See what changed, what needs attention, and the evidence behind each finding.</p>
              <div className="next-step-sequence" aria-label="Assessment workflow">Connect <span aria-hidden="true">/</span> Assess <span aria-hidden="true">/</span> Understand</div>
            </div>
            <div className="next-step-actions">
              <Link href={START.href} className="next-step-card next-step-primary">
                <span className="label-mono next-step-card-label">01 / Your code</span>
                <span className="next-step-card-title">{START.end}<span aria-hidden="true">↗</span></span>
                <span className="next-step-card-detail">Connect a repository and start an assessment.</span>
              </Link>
              <Link href="/lab" className="next-step-card">
                <span className="label-mono next-step-card-label">02 / The defense in action</span>
                <span className="next-step-card-title">Explore Defense Lab<span aria-hidden="true">↗</span></span>
                <span className="next-step-card-detail">Follow a test attack and the trained defender’s response.</span>
              </Link>
            </div>
          </section>
        </Reveal>
      </div>
    </>
  );
}
