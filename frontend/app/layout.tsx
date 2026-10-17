import type { Metadata } from 'next';
import { IBM_Plex_Mono, Inter, Space_Grotesk } from 'next/font/google';
import Link from 'next/link';
import type { ReactNode } from 'react';
import { BRAND_NAME, Wordmark } from '@/components/brand';
import { DemoBanner } from '@/components/demo-banner';
import { RollText } from '@/components/ui';
import './globals.css';

// Typography: Space Grotesk (headings), Inter (body, nav, buttons, metrics), IBM Plex Mono (code
// and technical data). Self-hosted by next/font at build time; exposed as CSS variables.
const inter = Inter({ subsets: ['latin'], weight: ['400', '500', '600'], display: 'swap', variable: '--font-inter' });
const spaceGrotesk = Space_Grotesk({ subsets: ['latin'], weight: ['500', '600', '700'], display: 'swap', variable: '--font-space-grotesk' });
const plexMono = IBM_Plex_Mono({ subsets: ['latin'], weight: ['400', '500', '600'], display: 'swap', variable: '--font-ibm-plex-mono' });

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
              <NavLink href="/lab" className="hdr-cta">Defense Lab</NavLink>
            </nav>
          </div>
        </header>
        <DemoBanner />
        <main id="main" className="mx-auto max-w-7xl px-4 py-6">{children}</main>
        <footer className="mx-auto max-w-7xl border-t border-line px-4 py-6 text-xs text-faint">
          Everything on these pages is read from the control-plane API or committed evaluation artifacts. Nothing is generated in the browser.
        </footer>
      </body>
    </html>
  );
}

function NavLink({ href, children, className = '' }: { href: string; children: string; className?: string }) {
  return (
    <Link
      href={href}
      className={`group label-mono inline-flex h-8 items-center rounded-md bg-brand/[0.06] px-3 text-ink transition-colors duration-[250ms] hover:bg-brand hover:text-on-brand ${className}`}
    >
      <RollText>{children}</RollText>
    </Link>
  );
}
