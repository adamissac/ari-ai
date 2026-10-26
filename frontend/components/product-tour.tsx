'use client';

import Image from 'next/image';
import { useEffect, useRef, useState } from 'react';

const STEPS = [
  {
    tab: '01 Connect',
    title: 'Connect a repository',
    copy: 'Pick a GitHub repo and branch. Ari reads the code and saves what it is supposed to do.',
    image: '/tour/connect.webp',
    alt: 'Ari repository picker showing repositories available to connect',
    url: 'ari / connect',
  },
  {
    tab: '02 Review',
    title: 'Review every commit',
    copy: 'Each finding shows the file and lines where it was found, and the fix that was checked.',
    image: '/tour/review.webp',
    alt: 'Ari code review tab showing a finding with file and line details',
    url: 'ari / projects / demo / commits / review',
  },
  {
    tab: '03 7 agents',
    title: 'Seven agents test it',
    copy: 'Scout, Probe, Trace, Diagnose, Patch, Fortify and Verify each do one job inside the scope you approve.',
    image: '/tour/agents.webp',
    alt: 'Ari commit page summarizing work from seven security agents',
    url: 'ari / projects / demo / commits / agents',
  },
  {
    tab: '04 Defense',
    title: 'Keep watching',
    copy: 'The defender recommends moves on your network map. Nothing is applied until you approve it.',
    image: '/tour/defense.webp',
    alt: 'Ari Defense Lab network map with recorded defender activity',
    url: 'ari / lab',
  },
] as const;

export function ProductTour() {
  const [active, setActive] = useState(0);
  const [paused, setPaused] = useState(false);
  const [inView, setInView] = useState(false);
  const [reduced, setReduced] = useState(false);
  const section = useRef<HTMLElement>(null);
  const remaining = useRef(7000);
  const playing = inView && !paused && !reduced;

  useEffect(() => {
    const el = section.current;
    if (!el || typeof IntersectionObserver === 'undefined') return;
    const observer = new IntersectionObserver(([entry]) => setInView(entry?.isIntersecting ?? false), { threshold: 0.2 });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    const frame = requestAnimationFrame(() => setReduced(query.matches));
    const update = () => setReduced(query.matches);
    query.addEventListener('change', update);
    return () => { cancelAnimationFrame(frame); query.removeEventListener('change', update); };
  }, []);

  useEffect(() => {
    if (!playing) return;
    const started = performance.now();
    const timer = window.setTimeout(() => {
      remaining.current = 7000;
      setActive(index => (index + 1) % STEPS.length);
    }, remaining.current);
    return () => {
      window.clearTimeout(timer);
      remaining.current = Math.max(0, remaining.current - (performance.now() - started));
    };
  }, [active, playing]);

  useEffect(() => { remaining.current = 7000; }, [active]);

  const move = (direction: number) => setActive(index => (index + direction + STEPS.length) % STEPS.length);
  const step = STEPS[active] ?? STEPS[0]!;

  return (
    <section
      ref={section}
      id="explainer"
      className="bleed bleed-night"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setPaused(false); }}
      aria-labelledby="tour-title"
    >
      <div className="mx-auto max-w-6xl px-6 py-16 md:px-12 md:py-20">
        <p className="kicker kicker-ghost">Product tour</p>
        <h2 id="tour-title" className="mt-3 text-3xl font-semibold md:text-4xl">See how Ari works</h2>
        <p className="mt-2 text-sm text-white/65">Four steps, from connecting a repo to watching it.</p>

        <div role="tablist" aria-label="Product tour steps" className="mt-8 grid grid-cols-2 gap-x-5 gap-y-4 md:grid-cols-4">
          {STEPS.map((item, index) => (
            <button
              key={item.tab}
              id={`tour-tab-${index}`}
              role="tab"
              aria-selected={active === index}
              aria-controls="tour-panel"
              tabIndex={active === index ? 0 : -1}
              type="button"
              className="product-tour-tab text-left"
              onClick={() => setActive(index)}
            >
              <span className="label-mono text-sm">{item.tab}</span>
              <span className="product-tour-progress" data-active={active === index || undefined} data-reduced={reduced || undefined} style={{ animationPlayState: playing && active === index ? 'running' : 'paused' }} />
            </button>
          ))}
        </div>

        <div id="tour-panel" role="tabpanel" aria-labelledby={`tour-tab-${active}`} className="mt-5 overflow-hidden rounded-xl border border-line bg-panel">
          <div className="flex items-center gap-3 border-b border-line px-4 py-3">
            <span className="product-tour-browser-dots" aria-hidden="true"><i /><i /><i /></span>
            <span className="label-mono truncate text-xs text-faint">{step.url}</span>
          </div>
          <Image src={step.image} alt={step.alt} width={1440} height={900} priority={active === 0} className="block h-auto w-full" />
          <div className="flex flex-col gap-5 border-t border-line px-5 py-5 md:flex-row md:items-end md:justify-between md:px-7">
            <div>
              <h3 className="text-lg font-semibold text-white">{step.title}</h3>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-white/65">{step.copy}</p>
            </div>
            <div className="flex shrink-0 gap-2">
              <button type="button" className="product-tour-nav" onClick={() => move(-1)}>Back</button>
              <button type="button" className="product-tour-nav product-tour-next" onClick={() => move(1)}>Next</button>
            </div>
          </div>
        </div>
        <p className="mt-3 text-xs text-white/40">Screens from a test project.</p>
      </div>
    </section>
  );
}
