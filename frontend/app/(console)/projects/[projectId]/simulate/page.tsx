'use client';

import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Suspense, useMemo } from 'react';
import { CommitAnalysis } from '@/components/demo/commit-analysis';
import { DemoMarker } from '@/components/demo/ui';
import { useProject } from '@/components/project';
import { Empty, Loading, PageTitle } from '@/components/ui';
import { api } from '@/lib/api';
import { simulatedAttack, type RealCommit } from '@/lib/simulated-attack';
import { useResource } from '@/lib/use-resource';

/**
 * Labelled simulated attack for a connected repository (ADR 0013). Live attacks run only
 * against a Python ASGI service in the sandbox; for anything else this replays what the
 * seven agents and the Defense Lab do, on illustrative data, and says so on the page.
 */
function Simulation() {
  const { selectedRepo } = useProject();
  const params = useSearchParams();
  const sha = params.get('sha');
  const repo = selectedRepo;
  // A clicked commit is looked up live so its real message and author frame the replay.
  const commits = useResource(repo && sha ? `commits:${repo.id}` : null, signal => api().repositoryCommits(repo!.id, { signal }));
  const real: RealCommit | undefined = commits.status === 'ready' ? commits.data.items.find(c => c.sha === sha) : undefined;
  const sim = useMemo(() => (repo ? simulatedAttack(repo.full_name, repo.default_branch, real) : null), [repo, real]);
  if (!repo || !sim) return (
    <div className="flex flex-col gap-6">
      <PageTitle eyebrow="Configure" title="Simulate" subtitle="An illustrative replay of the seven agents and Defense Lab for the selected repository." />
      <Empty><Link href="/connect" className="text-brand hover:underline">Connect a repository</Link> to open an illustrative attack walkthrough.</Empty>
    </div>
  );
  if (sha && commits.status === 'loading') return <Loading label="Loading the commit" />;
  return (
    <div data-testid="simulated-attack" className="commit-stage">
      <PageTitle eyebrow="Configure" title="Simulate" subtitle={<>Illustrative seven-agent replay for <span className="font-mono text-ink">{repo.full_name}</span>.</>} />
      <p className="mb-6 border-y border-line py-3 text-sm" data-testid="simulated-attack-note">
        <DemoMarker />
        <span className="min-w-0 text-muted">
          In this illustrative run, Ari AI&apos;s Probe agent performs <span className="text-ink">{sim.attack}</span> against an illustrative copy of <span className="font-mono text-ink">{repo.full_name}</span>{real && <> at <span className="font-mono text-ink">{real.sha.slice(0, 7)}</span></>}.
          Live attacks run only against Python ASGI services in the sandbox, so this replay uses illustrative code, findings and defense events. The commit header is real; nothing in the repository was attacked.
        </span>
      </p>
      <CommitAnalysis key={`${repo.full_name}@${sim.commit.sha}`} repo={sim.repo} commit={sim.commit} />
    </div>
  );
}

export default function SimulatedAttackPage() {
  return <Suspense fallback={null}><Simulation /></Suspense>;
}
