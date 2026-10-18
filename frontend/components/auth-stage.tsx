'use client';

import type { CSSProperties, ReactNode } from 'react';
import { BRAND_NAME, LogoMark } from '@/components/brand';
import { HeroStage } from '@/components/hero';
import { useMarkAuthStage } from '@/lib/auth-stage-presence';

const i = (n: number) => ({ '--i': n }) as CSSProperties;

/** Centered sign-in card over the animated hero background. */
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
  return (
    <HeroStage className="hero-full auth-stage px-5 pb-16 pt-36 sm:pt-28 md:px-12" labelledBy="auth-title">
      <div className="auth-orbits" aria-hidden="true"><span /><span /><span /></div>
      <div className="mx-auto w-full max-w-[460px]">
        <div className="auth-card hero-in w-full" style={i(1)} data-testid={testId}>
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
