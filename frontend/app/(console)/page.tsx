'use client';

import Link from 'next/link';
import { useState, type CSSProperties } from 'react';
import { BRAND_HEADLINE, BRAND_HEADLINE_REST } from '@/components/brand';
import { Reveal } from '@/components/reveal';
import { HowItWorks, ProblemScene, ProofStats, Walkthrough } from '@/components/story';
import { HeroStage, useLoopCursor } from '@/components/hero';
import { IntroLoader } from '@/components/intro-loader';
import { OptionalUserBar } from '@/components/user-bar';
import { DEMO_ONLY } from '@/lib/deployment';
import { RollText } from '@/components/ui';

const LOOP = ['Understand', 'Review', 'Attack Safely', 'Diagnose', 'Repair', 'Verify', 'Monitor'];

// A demo-only build has no backend, so the calls to action open the simulated demo instead.
const START = DEMO_ONLY ? { href: '/demo', hero: 'Try the demo', end: 'Try the demo' } : { href: '/projects', hero: 'Go to projects', end: 'Open projects' };

const i = (n: number) => ({ '--i': n }) as CSSProperties;

export default function HomePage() {
  const active = useLoopCursor(LOOP.length);
  const [revealed, setRevealed] = useState(false);

  return (
    <>
      <IntroLoader onReveal={() => setRevealed(true)} />
      <HeroStage className="hero-full px-6 pb-14 pt-44 md:px-12 md:pt-32" labelledBy="hero-title" play={revealed}>
        <div className="mx-auto w-full max-w-7xl text-center">
          <h1 id="hero-title" className="hero-headline display font-bold">
            <span data-spotlight className="hero-line hero-in" style={i(1)}>{BRAND_HEADLINE}</span><br />
            <span data-spotlight className="hero-line hero-line-dim hero-in text-white/70" style={i(2)}>{BRAND_HEADLINE_REST}</span>
          </h1>
          <div className="hero-in mt-10 flex flex-wrap justify-center gap-3" style={i(3)}>
            <Link href="/demo" className="group label-mono inline-flex h-11 items-center rounded-md bg-white px-4 text-ink transition-colors duration-[250ms] hover:bg-brand hover:text-on-brand">
              <RollText>Try the Demo</RollText>
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
          <section aria-labelledby="start-title" className="hero-ink rounded-2xl px-6 py-12 md:px-12">
            <h2 id="start-title" className="display max-w-2xl text-3xl font-semibold md:text-4xl">See it on a real change.</h2>
            <p className="mt-3 max-w-xl text-sm text-white/75">Open a project to connect a repository and start an assessment, or explore how the defense policy was evaluated.</p>
            <div className="mt-6 flex flex-wrap gap-2">
              <Link href={START.href} className="group label-mono inline-flex h-10 items-center rounded-md bg-white px-4 text-ink transition-colors duration-[250ms] hover:bg-brand hover:text-on-brand">
                <RollText>{START.end}</RollText>
              </Link>
              <Link href="/lab" className="group label-mono inline-flex h-10 items-center rounded-md bg-white/10 px-4 text-white transition-colors duration-[250ms] hover:bg-white/20">
                <RollText>Defense Lab</RollText>
              </Link>
            </div>
          </section>
        </Reveal>
      </div>
    </>
  );
}
