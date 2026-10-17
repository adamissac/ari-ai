import type { Metadata } from 'next';
import localFont from 'next/font/local';
import Link from 'next/link';
import type { ReactNode } from 'react';
import { BRAND_NAME, Wordmark } from '@/components/brand';
import { DemoBanner } from '@/components/demo-banner';
import { NavLink } from '@/components/nav-link';
import { SiteFooter } from '@/components/site-footer';
import { SmoothScroll } from '@/components/smooth-scroll';
import './globals.css';

// Packaged OFL fonts: no external font service is needed at build or runtime.
const inter = localFont({ src: './fonts/inter-latin-wght-normal.woff2', weight: '400 600', display: 'swap', variable: '--font-inter' });
const spaceGrotesk = localFont({ src: './fonts/space-grotesk-latin-wght-normal.woff2', weight: '500 700', display: 'swap', variable: '--font-space-grotesk' });
const plexMono = localFont({ src: [
  { path: './fonts/ibm-plex-mono-latin-400-normal.woff2', weight: '400', style: 'normal' },
  { path: './fonts/ibm-plex-mono-latin-500-normal.woff2', weight: '500', style: 'normal' },
  { path: './fonts/ibm-plex-mono-latin-600-normal.woff2', weight: '600', style: 'normal' },
], display: 'swap', variable: '--font-ibm-plex-mono' });

export const metadata: Metadata = {
  title: `${BRAND_NAME} Console`,
  description: 'Code intelligence, functional review, seven-agent security investigation and monitoring — backed by persisted evidence.',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${spaceGrotesk.variable} ${plexMono.variable}`}>
      <body className="min-h-screen antialiased">
        <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:rounded focus:bg-accent focus:px-2 focus:py-1 focus:text-bg">Skip to content</a>
        <header className="site-header sticky top-0 z-40 border-b border-line/80 bg-white/80 backdrop-blur-md">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3">
            <Link href="/" aria-label={`${BRAND_NAME} home`} className="hdr-reveal">
              <Wordmark priority />
            </Link>
            <nav aria-label="Primary" className="flex items-center gap-1.5">
              <NavLink href="/projects" className="hdr-reveal">Projects</NavLink>
              <NavLink href="/lab" className="hdr-reveal">Defense Lab</NavLink>
              <NavLink href="/demo" className="hdr-reveal">Demo</NavLink>
              <NavLink href="/pricing" className="hdr-cta">Pricing</NavLink>
            </nav>
          </div>
        </header>
        <SmoothScroll />
        <DemoBanner />
        <main id="main" className="mx-auto max-w-7xl px-4 py-6">{children}</main>
        <SiteFooter />
      </body>
    </html>
  );
}

