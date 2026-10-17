'use client';

import Link from 'next/link';
import { useState, type CSSProperties } from 'react';
import { BRAND_HEADLINE, BRAND_HEADLINE_REST, BRAND_NAME } from '@/components/brand';
import { Reveal } from '@/components/reveal';
import { HeroStage, useLoopCursor } from '@/components/hero';
import { IntroLoader } from '@/components/intro-loader';
import { UserBar } from '@/components/user-bar';
import { RollText } from '@/components/ui';

const PILLARS = [
  { n: '01', title: 'Does it work as intended?', body: 'The Reviewer agent builds intent evidence from specs, tests and the change, then reproduces functional defects with executed tests.' },
  { n: '02', title: 'Can an attacker exploit it?', body: 'Seven separate security agents — Scout, Probe, Trace, Diagnose, Patch, Verify, Fortify — investigate inside an approved sandbox scope.' },
  { n: '03', title: 'Does it stay secure?', body: 'Signed GitHub events trigger durable re-assessment. A Double DQN policy trained in simulation offers labelled decision support.' },
];
const LOOP = ['Understand', 'Review', 'Attack safely', 'Diagnose', 'Repair', 'Verify', 'Monitor'];
const STEPS: Record<string, string> = {
  Understand: 'Code intelligence indexes the repository and extracts what the software is supposed to do from specs, docs, tests and history.',
  Review: 'The Reviewer checks each change against that intent and writes tests that reproduce functional defects on the real code.',
  'Attack safely': 'Scout maps the attack surface and Probe tests it, only inside an approved scope and an isolated sandbox.',
  Diagnose: 'Trace follows the evidence to the vulnerable path and Diagnose explains the root cause, with source spans.',
  Repair: 'After a human approves remediation, Patch proposes the smallest fix in an isolated copy of the code.',
  Verify: 'Verify replays independent tests on a fresh checkout. A finding closes only when executed tests agree.',
  Monitor: 'Signed GitHub events re-run the assessment as code changes. Fortify hardens what was learned.',
};
const PRINCIPLES = [
  { title: 'Executed tests decide', body: 'No model output counts as proof, including ours. Statuses change only when real tests run and agree.' },
  { title: 'Safety boundaries are code', body: 'Authorized scopes, sandbox limits and human approval gates are enforced deterministically, not by prompts.' },
  { title: 'Every claim has evidence', body: 'Findings cite source spans, test reports and transcripts that are persisted and shown as they were recorded.' },
];

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
            <Link href="/projects" className="group label-mono inline-flex h-10 items-center rounded-md bg-white px-4 text-ink transition-colors duration-[250ms] hover:bg-brand hover:text-on-brand">
              <RollText>Go to projects</RollText>
            </Link>
            <a href="#how" className="group label-mono inline-flex h-10 items-center rounded-md bg-white/10 px-4 text-white backdrop-blur transition-colors duration-[250ms] hover:bg-white/20">
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

      <div className="hero-cover pt-6">
        <UserBar />

        <section aria-labelledby="what-title" className="py-10">
          <p className="label-mono text-brand">What {BRAND_NAME} answers</p>
          <h2 id="what-title" className="display mt-3 max-w-3xl text-3xl font-semibold md:text-4xl">Three questions about every change.</h2>
          <div className="mt-8 grid gap-3 md:grid-cols-3">
            {PILLARS.map((p, n) => (
              <Reveal key={p.n} delay={n * 90}>
                <div className="group h-full rounded-xl border border-line bg-panel p-5 transition-[border-color,box-shadow,transform] duration-300 hover:-translate-y-0.5 hover:border-brand/40 hover:shadow-[0_12px_28px_-16px_rgba(194,69,45,0.45)]">
                  <p className="label-mono text-brand">{p.n}</p>
                  <p className="mt-3 text-lg font-semibold tracking-tight">{p.title}</p>
                  <p className="mt-2 text-sm text-muted">{p.body}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </section>

        <section id="how" aria-labelledby="how-title" className="scroll-mt-20 py-10">
          <p className="label-mono text-brand">How it works</p>
          <h2 id="how-title" className="display mt-3 max-w-3xl text-3xl font-semibold md:text-4xl">From a change to a verified fix, in seven steps.</h2>
          <ol className="mt-8 grid gap-px overflow-hidden rounded-xl border border-line bg-line md:grid-cols-2 lg:grid-cols-4">
            {LOOP.map((step, n) => (
              <li key={step} className="bg-panel">
                <Reveal delay={(n % 4) * 80} className="h-full p-5">
                  <p className="label-mono text-faint">{String(n + 1).padStart(2, '0')}</p>
                  <p className="mt-2 text-base font-semibold tracking-tight">{step}</p>
                  <p className="mt-1.5 text-sm text-muted">{STEPS[step]}</p>
                </Reveal>
              </li>
            ))}
            <li className="hidden bg-panel-2 p-5 lg:flex lg:items-end">
              <p className="label-mono text-brand">Then the loop starts again on the next change.</p>
            </li>
          </ol>
        </section>

        <section aria-labelledby="proof-title" className="py-10">
          <p className="label-mono text-brand">Proof, not promises</p>
          <h2 id="proof-title" className="display mt-3 max-w-3xl text-3xl font-semibold md:text-4xl">Built so you can check every answer.</h2>
          <div className="mt-8 grid gap-3 md:grid-cols-3">
            {PRINCIPLES.map((p, n) => (
              <Reveal key={p.title} delay={n * 90}>
                <div className="h-full border-l-2 border-brand pl-4">
                  <p className="text-lg font-semibold tracking-tight">{p.title}</p>
                  <p className="mt-2 text-sm text-muted">{p.body}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </section>

        <Reveal className="my-10">
          <section aria-labelledby="start-title" className="hero-ink rounded-2xl px-6 py-12 md:px-12">
            <h2 id="start-title" className="display max-w-2xl text-3xl font-semibold md:text-4xl">See it on a real change.</h2>
            <p className="mt-3 max-w-xl text-sm text-white/75">Open a project to connect a repository and start an assessment, or explore how the defense policy was trained.</p>
            <div className="mt-6 flex flex-wrap gap-2">
              <Link href="/projects" className="group label-mono inline-flex h-10 items-center rounded-md bg-white px-4 text-ink transition-colors duration-[250ms] hover:bg-brand hover:text-on-brand">
                <RollText>Open projects</RollText>
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
