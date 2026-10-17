'use client';

import { useParams } from 'next/navigation';
import { CommitAnalysis } from '@/components/demo/commit-analysis';
import { DemoBar } from '@/components/demo/ui';
import { Empty } from '@/components/ui';
import { DEMO_ORGS, findCommit, findRepo } from '@/lib/demo/data';
import { useDemoGate } from '@/lib/demo/gate';

export default function DemoCommitPage() {
  const { org, repo: name, sha } = useParams<{ org: string; repo: string; sha: string }>();
  const session = useDemoGate();
  const repo = findRepo(org, name);
  const commit = repo ? findCommit(repo, sha) : undefined;
  if (!session.user) return <div className="min-h-[60vh]" />;
  if (!repo || !commit) return <Empty>Commit not found.</Empty>;
  const orgName = DEMO_ORGS.find(o => o.login === org)?.name ?? org;
  return (
    <div data-testid="demo-commit" className="commit-stage">
      <DemoBar
        crumbs={[{ href: '/demo', label: 'Organizations' }, { href: `/demo/${org}`, label: orgName }, { href: `/demo/${org}/${repo.name}`, label: repo.name }, { label: commit.sha.slice(0, 7) }]}
        user={session.user}
        onSignOut={session.signOut}
      />
      <CommitAnalysis key={commit.sha} repo={repo} commit={commit} />
    </div>
  );
}
