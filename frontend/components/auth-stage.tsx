'use client';

import type { CSSProperties, ReactNode } from 'react';
import { BRAND_HEADLINE, BRAND_HEADLINE_REST, BRAND_NAME, BRAND_TAGLINE, LogoMark } from '@/components/brand';
import { ASSESSMENT_LOOP, HeroStage, useLoopCursor } from '@/components/hero';
import { useMarkAuthStage } from '@/lib/auth-stage-presence';

const i = (n: number) => ({ '--i': n }) as CSSProperties;

/**
 * Full-screen sign-in surface on the home hero's stage: dark ink, drifting light orbs,
 * pointer glow and the spotlit headline on the left; a glass card with the sign-in actions
 * on the right (stacked on phones).
 */
export function AuthStage({
  kicker = `Welcome to ${BRAND_NAME}`,
  title,
  subtitle,
  children,
  footnote,
  testId,
}: {
  kicker?: string;
  title: string;
  subtitle?: ReactNode;
  children: ReactNode;
  footnote?: ReactNode;
  testId?: string;
}) {
  useMarkAuthStage();
  const active = useLoopCursor(ASSESSMENT_LOOP.length);
  return (
    <HeroStage className="hero-full auth-stage px-5 pb-16 pt-36 sm:pt-28 md:px-12" labelledBy="auth-title">
      <div className="mx-auto grid w-full max-w-6xl items-center gap-10 lg:grid-cols-[1.2fr_1fr] lg:gap-16">
        <div className="text-center lg:text-left">
          <p className="hero-in label-mono text-white/70" style={i(0)}>{BRAND_NAME} · software assurance</p>
          <p className="hero-headline auth-headline display mt-4 font-bold" aria-hidden="true">
            <span data-spotlight className="hero-line hero-in" style={i(1)}>{BRAND_HEADLINE}</span><br />
            <span data-spotlight className="hero-line hero-line-dim hero-in" style={i(2)}>{BRAND_HEADLINE_REST}</span>
          </p>
          <p className="hero-in mx-auto mt-5 max-w-md text-[15px] leading-relaxed text-white/80 lg:mx-0" style={i(3)}>{BRAND_TAGLINE}</p>
          <ol aria-label="Assessment loop" className="hero-in mt-8 hidden flex-wrap gap-1.5 lg:flex" style={i(4)}>
            {ASSESSMENT_LOOP.map((step, n) => (
              <li key={step} data-active={active === n || undefined} className="hero-step label-mono flex items-center gap-1.5 rounded-md bg-white/10 px-2.5 py-1 text-white/85 backdrop-blur transition-colors duration-[250ms]">
                <span className="text-white/50">{String(n + 1).padStart(2, '0')}</span>{step}
              </li>
            ))}
          </ol>
        </div>

        <div className="auth-card hero-in w-full justify-self-center lg:max-w-md lg:justify-self-end" style={i(2)} data-testid={testId}>
          <div className="flex items-center gap-2.5">
            <LogoMark size={22} decorative priority />
            <p className="label-mono auth-kicker">{kicker}</p>
          </div>
          <h1 id="auth-title" className="mt-3 text-[1.75rem] font-semibold leading-tight tracking-[-0.02em] text-white">{title}</h1>
          {subtitle && <p className="mt-2 text-sm leading-relaxed text-white/70">{subtitle}</p>}
          <div className="mt-7">{children}</div>
          {footnote && <div className="auth-footnote mt-7">{footnote}</div>}
        </div>
      </div>
    </HeroStage>
  );
}

/** A small padlock for footnotes. */
export function LockIcon() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true" className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.5">
      <rect x="3" y="7" width="10" height="7" rx="1.6" />
      <path d="M5.5 7V5a2.5 2.5 0 015 0v2" strokeLinecap="round" />
    </svg>
  );
}
