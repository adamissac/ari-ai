'use client';

import type { ReactNode } from 'react';
import { BRAND_NAME, LogoMark } from '@/components/brand';
import { HeroStage } from '@/components/hero';
import { useMarkAuthStage } from '@/lib/auth-stage-presence';

/** Centered sign-in card over the animated hero background. */
export function AuthStage({
  kicker = BRAND_NAME,
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
    <HeroStage className="auth-stage px-5 py-16 md:px-12" labelledBy="auth-title">
      <div className="auth-orbits" aria-hidden="true"><span /><span /><span /></div>
      <div className="mx-auto w-full max-w-[460px]">
        <div className="auth-card w-full" data-testid={testId}>
          <div className="flex items-center gap-2.5">
            <LogoMark size={22} decorative priority />
            <p className="label-mono auth-kicker">{kicker}</p>
          </div>
          <h1 id="auth-title" className="mt-3 text-[1.75rem] font-medium leading-tight tracking-[-0.02em] text-ink">{title}</h1>
          {subtitle && <p className="mt-2 text-sm leading-relaxed text-muted">{subtitle}</p>}
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
