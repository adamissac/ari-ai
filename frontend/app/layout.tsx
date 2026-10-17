import type { Metadata } from 'next';
import Link from 'next/link';
import type { ReactNode } from 'react';
import { DemoBanner } from '@/components/demo-banner';
import './globals.css';

export const metadata: Metadata = {
  title: 'Agentic Security Console',
  description: 'Code intelligence, functional review, seven-agent security investigation and monitoring — backed by persisted evidence.',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:rounded focus:bg-accent focus:px-2 focus:py-1 focus:text-bg">Skip to content</a>
        <header className="border-b border-line bg-panel/80 backdrop-blur">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3">
            <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
              <span aria-hidden="true" className="grid h-6 w-6 place-items-center rounded bg-gradient-to-br from-accent to-indigo text-xs font-bold text-bg">AS</span>
              Agentic Security
            </Link>
            <nav aria-label="Primary" className="flex items-center gap-4 text-sm text-muted">
              <Link className="hover:text-accent" href="/">Projects</Link>
              <Link className="hover:text-accent" href="/lab">Defense Lab</Link>
            </nav>
          </div>
        </header>
        <DemoBanner />
        <main id="main" className="mx-auto max-w-7xl px-4 py-6">{children}</main>
        <footer className="mx-auto max-w-7xl px-4 pb-8 text-xs text-faint">
          Everything on these pages is read from the control-plane API or committed evaluation artifacts. Nothing is generated in the browser.
        </footer>
      </body>
    </html>
  );
}
