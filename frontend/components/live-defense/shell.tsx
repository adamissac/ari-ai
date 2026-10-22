'use client';

import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import type { ReactNode } from 'react';
import { EnforcementNote, PreviewBanner, SourceTag } from '@/components/live-defense/common';
import { liveDefenseHref, liveDefenseMode, liveDefenseTab, withLiveDefenseMode, type LiveDefenseMode } from '@/lib/live-defense';

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'incidents', label: 'Investigation' },
  { id: 'explain', label: 'Explainability' },
] as const;

export function LiveDefenseShell({
  projectId,
  children,
  standalone = false,
}: {
  projectId: string | null;
  children: ReactNode;
  standalone?: boolean;
}) {
  const pathname = usePathname();
  const params = useSearchParams();
  const router = useRouter();
  const mode: LiveDefenseMode = standalone ? 'layout-preview' : liveDefenseMode(params.get('preview'));
  const tab = liveDefenseTab(pathname);
  const toggle = () => {
    if (standalone) return;
    const next: LiveDefenseMode = mode === 'live' ? 'layout-preview' : 'live';
    router.replace(withLiveDefenseMode(pathname, next));
  };

  return (
    <div className="flex flex-col gap-4" data-testid="live-defense" data-mode={mode}>
      <header className="monitor-head" data-testid="live-defense-head">
        <div>
          <p className="label-mono text-white/60">Live Defense · phase 1</p>
          <h2 className="mt-1 text-xl font-semibold tracking-tight text-white">What is recorded, and what is still missing</h2>
          <p className="mt-1 max-w-2xl text-sm text-white/70">
            Customer view of continuous defense. Live mode shows control-plane records only.
            There is no live component map, no autonomous enforcement, and no fabricated confidence score.
          </p>
        </div>
        <div className="flex flex-col items-start gap-3 lg:items-end">
          <SourceTag mode={mode} />
          {!standalone && (
            <button
              type="button"
              className="rounded-full border border-white/15 bg-white/5 px-3.5 py-2 text-sm text-white hover:bg-white/10"
              data-testid="live-defense-preview-toggle"
              aria-pressed={mode === 'layout-preview'}
              onClick={toggle}
            >
              {mode === 'layout-preview' ? 'Leave sample layout' : 'Open sample layout'}
            </button>
          )}
        </div>
      </header>
      {mode === 'layout-preview' && <PreviewBanner />}
      <EnforcementNote />
      <nav aria-label="Live Defense" className="ld-tabs">
        {TABS.map(item => {
          const href = liveDefenseHref(standalone ? null : projectId, item.id, mode);
          const active = tab === item.id;
          return (
            <Link key={item.id} href={href} aria-current={active ? 'page' : undefined} className="ld-tab label-mono">
              {item.label}
            </Link>
          );
        })}
      </nav>
      {children}
    </div>
  );
}
