'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { BRAND_NAME, LogoMark } from '@/components/brand';
import { RecordedLiveRun } from '@/components/demo/recorded-live-run';
import { Avatar, DemoBar, DemoMarker, GitHubMark } from '@/components/demo/ui';
import { DEMO_ORGS, reposFor } from '@/lib/demo/data';
import { useDemoSession } from '@/lib/demo/session';

const SCOPES = ['Read repository contents and commit history', 'Read organization membership', 'Receive push events (webhook)'];

export default function DemoSignInPage() {
  const { user, ready, signIn, signOut } = useDemoSession();
  const [authorizing, setAuthorizing] = useState(false);

  useEffect(() => {
    if (!authorizing) return;
    const id = setTimeout(() => { signIn(); setAuthorizing(false); }, 1400);
    return () => clearTimeout(id);
  }, [authorizing, signIn]);

  if (!ready) return <div className="min-h-[60vh]" />;

  if (!user) {
    return (
      <>
      <div className="mx-auto mt-6 grid max-w-5xl overflow-hidden rounded-3xl md:grid-cols-[1.1fr_1fr]" data-testid="demo-signin">
        <section className="demo-ink flex flex-col justify-between gap-10 p-8 md:p-10">
          <div className="flex items-center justify-between gap-3"><LogoMark size={26} className="text-white" /><DemoMarker /></div>
          <div>
            <p className="label-mono text-white/60">Continuous software assurance</p>
            <h1 className="display mt-3 text-3xl font-semibold md:text-[2.6rem]">Every commit, reviewed, attacked safely and proven fixed.</h1>
            <ul className="mt-6 flex flex-col gap-2.5 text-sm text-white/75">
              <li className="flex gap-2"><span aria-hidden="true" className="text-brand">→</span>Intent-aware code review on every push</li>
              <li className="flex gap-2"><span aria-hidden="true" className="text-brand">→</span>Seven security agents in an approved sandbox</li>
              <li className="flex gap-2"><span aria-hidden="true" className="text-brand">→</span>A simulated defense policy that recommends responses</li>
            </ul>
          </div>
          <p className="text-xs text-white/50">This walkthrough uses illustrative accounts and repositories. No GitHub data is read.</p>
        </section>
        <section className="flex flex-col justify-center border border-line bg-white p-8 md:rounded-r-3xl md:border-l-0 md:p-10">
          <p className="label-mono text-brand">Welcome to {BRAND_NAME}</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight">Sign in to continue</h2>
          <p className="mt-1.5 text-sm text-muted">Connect GitHub to choose an organization and a repository.</p>
          <button
            type="button"
            onClick={() => setAuthorizing(true)}
            disabled={authorizing}
            className="mt-7 flex h-11 w-full items-center justify-center gap-2.5 rounded-lg bg-[#1c1210] px-4 text-sm font-medium text-white transition-colors duration-200 hover:bg-brand disabled:opacity-80"
            data-testid="demo-github-signin"
          >
            {authorizing ? <><span aria-hidden="true" className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />Authorizing with GitHub…</> : <><GitHubMark />Continue with GitHub</>}
          </button>
          <div className="mt-6 rounded-xl border border-line bg-panel-2 p-4">
            <p className="text-xs font-semibold text-ink">{BRAND_NAME} will request</p>
            <ul className="mt-2 flex flex-col gap-1.5 text-xs text-muted">
              {SCOPES.map(scope => <li key={scope} className="flex gap-2"><span aria-hidden="true" className="text-ok">✓</span>{scope}</li>)}
            </ul>
            <p className="mt-3 text-xs text-faint">Read-only. {BRAND_NAME} never pushes to your default branch; fixes arrive as pull requests.</p>
          </div>
        </section>
      </div>
      <div className="mx-auto max-w-5xl"><RecordedLiveRun /></div>
      </>
    );
  }

  return (
    <div data-testid="demo-orgs">
      <DemoBar crumbs={[{ label: 'Choose an organization' }]} user={user} onSignOut={signOut} />
      <header className="mb-6">
        <p className="label-mono text-brand">Signed in as {user.login}</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Where should {BRAND_NAME} look?</h1>
        <p className="mt-1.5 text-sm text-muted">Pick an organization. You can connect more later from settings.</p>
      </header>
      <ul className="grid gap-3 md:grid-cols-3">
        {DEMO_ORGS.map((org, i) => {
          const repos = reposFor(org.login);
          return (
            <li key={org.login} className="demo-rise" style={{ ['--i' as string]: i }}>
              <Link href={`/demo/${org.login}`} className="demo-card group flex h-full flex-col gap-4 p-5" data-testid={`demo-org-${org.login}`}>
                <span className="flex items-center gap-3">
                  <Avatar login={org.login} size={40} />
                  <span className="min-w-0">
                    <span className="block truncate font-semibold">{org.name}</span>
                    <span className="block truncate font-mono text-xs text-muted">{org.login}</span>
                  </span>
                </span>
                <span className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
                  <span>{repos.length} {repos.length === 1 ? 'repository' : 'repositories'}</span>
                  <span>{org.members} {org.members === 1 ? 'member' : 'members'}</span>
                  <span>{org.kind === 'personal' ? 'Personal account' : `${org.plan} plan`}</span>
                </span>
                <span className="mt-auto text-sm font-medium text-brand">Open <span aria-hidden="true" className="inline-block transition-transform group-hover:translate-x-1">→</span></span>
              </Link>
            </li>
          );
        })}
      </ul>
      <RecordedLiveRun />
    </div>
  );
}
