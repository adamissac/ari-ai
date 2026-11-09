'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { AuthStage, LockIcon } from '@/components/auth-stage';
import { BRAND_NAME } from '@/components/brand';
import { Avatar, GitHubMark } from '@/components/demo/ui';
import { DEMO_GITHUB_REPOS } from '@/lib/demo/console/state';

const PERMISSIONS = [
  ['Contents', 'Read & write', 'Read code to review; write only to open the build-recipe PR and fix PRs you approve.'],
  ['Pull requests', 'Read & write', 'Open those PRs and leave review comments if you turn comments on.'],
  ['Metadata', 'Read-only', 'Repository names and default branches.'],
  ['Events', 'Push, pull request', 'Only for reviews you switch on; automatic reviews start off.'],
] as const;

/**
 * The demo account's stand-in for "Continue with GitHub": the same permissions a real
 * install asks for, on the fictional Lumen Pay organization. Nothing is sent to GitHub.
 */
export function GitHubStep({ next }: { next: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const authorize = () => {
    setBusy(true);
    setTimeout(() => router.replace(next), 900);
  };
  return (
    <AuthStage
      kicker="Demo account · step 1 of 4"
      title={`Connect GitHub to ${BRAND_NAME}`}
      subtitle={<>A real sign-in continues with GitHub and installs the {BRAND_NAME} GitHub App. Here it is simulated for the fictional <strong className="text-white">lumen-pay</strong> organization: no GitHub account is used.</>}
      testId="demo-github-step"
      footnote={<><LockIcon /><span>Sample data only. Nothing is read from or written to GitHub, and no repository outside this demo can be reached.</span></>}
    >
      <div className="flex items-center gap-3 rounded-lg border border-white/15 bg-white/5 p-3">
        <Avatar login="lumen-pay" size={36} />
        <div className="min-w-0 text-sm">
          <p className="font-semibold text-white">lumen-pay</p>
          <p className="text-white/60">{DEMO_GITHUB_REPOS.length} repositories selected for the {BRAND_NAME} GitHub App</p>
        </div>
      </div>
      <p className="label-mono mt-5 text-xs text-white/55">{BRAND_NAME} will be able to</p>
      <dl className="mt-2 divide-y divide-white/10 text-sm">
        {PERMISSIONS.map(([name, level, why]) => (
          <div key={name} className="py-2.5">
            <dt className="flex items-center justify-between gap-3 text-white"><span>{name}</span><span className="font-mono text-xs text-white/60">{level}</span></dt>
            <dd className="mt-0.5 text-xs text-white/55">{why}</dd>
          </div>
        ))}
      </dl>
      <button type="button" className="auth-btn auth-btn-light mt-6 bg-white" disabled={busy} onClick={authorize} data-testid="demo-github-authorize">
        {busy ? <><span aria-hidden="true" className="h-4 w-4 animate-spin rounded-full border-2 border-black/20 border-t-black" />Connecting</> : <><GitHubMark className="h-[18px] w-[18px]" /><span>Authorize and install (simulated)</span></>}
      </button>
    </AuthStage>
  );
}
