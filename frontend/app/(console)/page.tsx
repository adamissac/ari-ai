'use client';

import Link from 'next/link';
import { useState, type CSSProperties } from 'react';
import { BRAND_HEADLINE, BRAND_HEADLINE_REST, BRAND_NAME } from '@/components/brand';
import { Reveal } from '@/components/reveal';
import { HowItWorks, ProblemScene, ProofStats, Walkthrough } from '@/components/story';
import { HeroStage, useLoopCursor } from '@/components/hero';
import { IntroLoader } from '@/components/intro-loader';
import { UserBar } from '@/components/user-bar';
import { RollText } from '@/components/ui';

const LOOP = ['Understand', 'Review', 'Attack safely', 'Diagnose', 'Repair', 'Verify', 'Monitor'];

const i = (n: number) => ({ '--i': n }) as CSSProperties;

export default function HomePage() {
  const active = useLoopCursor(LOOP.length);
  const [revealed, setRevealed] = useState(false);

  return (
    <>
      <IntroLoader onReveal={() => setRevealed(true)} />
      <HeroStage className="hero-full px-6 pb-14 pt-24 md:px-12" labelledBy="hero-title" play={revealed}>
        <div className="mx-auto w-full max-w-7xl">
          <p className="hero-in label-mono flex items-center gap-2 text-white/70" style={i(0)}>
            <span aria-hidden="true" className="hero-ping" />{BRAND_NAME} · software assurance
          </p>
          <h1 id="hero-title" className="display mt-4 max-w-4xl text-4xl font-semibold md:text-6xl">
            <span data-spotlight className="hero-line hero-in" style={i(1)}>{BRAND_HEADLINE}</span><br />
            <span data-spotlight className="hero-line hero-line-dim hero-in text-white/70" style={i(2)}>{BRAND_HEADLINE_REST}</span>
          </h1>
          <p className="hero-in mt-5 max-w-2xl text-sm text-white/75 md:text-base" style={i(3)}>
            {BRAND_NAME} learns what your software is supposed to do, tests it like an attacker inside an approved sandbox,
            and only calls a repair done when independent, executed tests agree.
          </p>
          <div className="hero-in mt-8 flex flex-wrap gap-2" style={i(4)}>
            <Link href="/projects" className="group label-mono inline-flex h-10 items-center rounded-md bg-white px-4 text-ink transition-all duration-[250ms] hover:bg-brand hover:text-on-brand hover:shadow-lg hover:-translate-y-0.5">
              <RollText>Go to projects</RollText>
            </Link>
            <a href="#how" className="group label-mono inline-flex h-10 items-center rounded-md bg-white/10 px-4 text-white backdrop-blur transition-all duration-[250ms] hover:bg-white/20 hover:shadow-lg hover:-translate-y-0.5">
              <RollText>How it works</RollText>
            </a>
          </div>
          <ol aria-label="Assessment loop" className="hero-in mt-8 flex flex-wrap gap-1.5" style={i(5)}>
            {LOOP.map((step, n) => (
              <li key={step} data-active={active === n || undefined} className="hero-step label-mono flex items-center gap-1.5 rounded-md bg-white/10 px-2.5 py-1 text-white/85 backdrop-blur transition-colors duration-[250ms] hover:bg-white/20">
                <span className="text-white/50">{String(n + 1).padStart(2, '0')}</span>{step}
              </li>
            ))}
          </ol>
        </div>
      </HeroStage>

      <div className="hero-cover -mb-6 pb-30 pt-6 md:pb-38">
        <UserBar />

        <ProblemScene />
        <HowItWorks />
        <Walkthrough />
        <ProofStats />

        <Reveal className="mt-10">
          <section aria-labelledby="start-title" className="hero-ink rounded-2xl px-6 py-12 md:px-12 shadow-xl">
            <h2 id="start-title" className="display max-w-2xl text-3xl font-semibold md:text-4xl">See it on a real change.</h2>
            <p className="mt-3 max-w-xl text-sm text-white/75">Open a project to connect a repository and start an assessment, or explore how the defense policy was evaluated.</p>
            <div className="mt-6 flex flex-wrap gap-2">
              <Link href="/projects" className="group label-mono inline-flex h-10 items-center rounded-md bg-white px-4 text-ink transition-all duration-[250ms] hover:bg-brand hover:text-on-brand hover:shadow-lg hover:-translate-y-0.5">
                <RollText>Open projects</RollText>
              </Link>
              <Link href="/lab" className="group label-mono inline-flex h-10 items-center rounded-md bg-white/10 px-4 text-white transition-all duration-[250ms] hover:bg-white/20 hover:shadow-lg hover:-translate-y-0.5">
                <RollText>Defense Lab</RollText>
              </Link>
            </div>
          </section>
        </Reveal>
      </div>
    </>
  );
}
