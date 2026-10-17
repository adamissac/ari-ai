'use client';

import { useSearchParams } from 'next/navigation';
import { Suspense, useMemo } from 'react';
import { CommitAnalysis } from '@/components/demo/commit-analysis';
import { DemoMarker } from '@/components/demo/ui';
import { useProject } from '@/components/project';
import { Empty } from '@/components/ui';
import { simulatedAttack } from '@/lib/simulated-attack';

/**
 * Labelled simulated attack for a connected repository (ADR 0013). Live attacks run only
 * against a Python ASGI service in the sandbox; for anything else this replays what the
 * seven agents and the Defense Lab do, on illustrative data, and says so on the page.
 */
function Simulation() {
  const { repos } = useProject();
  const name = useSearchParams().get('repo');
  const repo = repos.find(r => r.full_name === name) ?? repos[0];
  const sim = useMemo(() => (repo ? simulatedAttack(repo.full_name, repo.default_branch) : null), [repo]);
  if (!repo || !sim) return <Empty>Connect a repository to run a simulated attack.</Empty>;
  return (
    <div data-testid="simulated-attack">
      <div className="mb-4 flex flex-wrap items-start gap-3 rounded-xl border border-line bg-panel-2 px-4 py-3 text-sm" data-testid="simulated-attack-note">
        <DemoMarker />
        <p className="min-w-0 flex-1 text-muted">
          Ari AI had its Probe agent perform <span className="text-ink">{sim.attack}</span> in a simulated run for <span className="font-mono text-ink">{repo.full_name}</span>.
          Live attacks run only against Python ASGI services in the sandbox, so this replay uses illustrative code, findings and defense events. Nothing in the repository was read or attacked.
        </p>
      </div>
      <CommitAnalysis key={repo.full_name} repo={sim.repo} commit={sim.commit} />
    </div>
  );
}

export default function SimulatedAttackPage() {
  return <Suspense fallback={null}><Simulation /></Suspense>;
}
