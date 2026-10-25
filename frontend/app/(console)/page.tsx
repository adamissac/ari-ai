'use client';

import Link from 'next/link';
import { LandingFooter } from '@/components/landing-footer';
import { SignalField } from '@/components/marketing/signal-field';
import { OptionalUserBar } from '@/components/user-bar';
import { DEMO_ONLY } from '@/lib/deployment';

// A demo-only build has no backend, so the calls to action open the access-code sign-in.
const START = DEMO_ONLY ? { href: '/access', label: 'Sign in' } : { href: '/projects', label: 'Go to projects' };

type Agent = { name: string; does: string; runs: string; writes: string; on?: [boolean, boolean] };
const BANDS: Array<{ title: string; body: string; agents: Agent[] }> = [
  {
    title: 'Functional review',
    body: 'Does the change do what the repository says it should?',
    agents: [
      { name: 'Reviewer', does: 'Reads the diff against the indexed repository and its expectations, and writes tests that reproduce defects.', runs: 'Tests only', writes: 'Tests only', on: [true, true] },
    ],
  },
  {
    title: 'Security validation',
    body: 'Only inside a scope a human approved. Hypotheses stay hypotheses until a check runs.',
    agents: [
      { name: 'Scout', does: 'Maps endpoints, data flows and trust boundaries.', runs: 'No', writes: 'No' },
      { name: 'Probe', does: 'Executes harmless checks against the copy Ari builds of your app.', runs: 'Scoped sandbox', writes: 'Harnesses only', on: [true, true] },
      { name: 'Trace', does: 'Links individual steps into one exploitable path.', runs: 'No', writes: 'No' },
      { name: 'Diagnose', does: 'Pins the defect to source spans and explains why it happens.', runs: 'No', writes: 'No' },
    ],
  },
  {
    title: 'Repair and verification',
    body: 'A fix exists only after approval, and counts only after an independent run.',
    agents: [
      { name: 'Patch', does: 'Proposes the smallest fix in an isolated worktree, after a human approves.', runs: 'Worktree sandbox', writes: 'Isolated worktree', on: [true, true] },
      { name: 'Fortify', does: 'Suggests regression tests and hardening config.', runs: 'Static tools', writes: 'Suggestions', on: [false, true] },
      { name: 'Verify', does: 'Replays the exploit and the suite on a fresh checkout. Shares nothing with Patch.', runs: 'Fresh sandbox', writes: 'No', on: [true, false] },
    ],
  },
];

const STATES: Array<[string, string, string, string]> = [
  ['FLAGGED', 'tone-signal', 'A reviewer or agent thinks something is wrong.', 'Nothing has run yet. It is a hypothesis, and Ari labels it as one.'],
  ['VALIDATED', 'tone-bad', 'A check executed and reproduced the problem.', 'Probe repeats it; a failure only counts if it fails the same way twice.'],
  ['INCONCLUSIVE', 'tone-muted', 'The check ran but could not decide.', 'It stays a hypothesis with its evidence attached. No fix is proposed from it.'],
  ['FIX PROPOSED', 'tone-warn', 'Patch wrote a candidate fix after a human approved.', 'It sits in an isolated worktree. Nothing reaches your repository yet.'],
  ['VERIFIED', 'tone-ok', 'Verify replayed the exploit and the tests on a fresh checkout.', 'The exploit no longer works and the suite passes.'],
  ['FAILED', 'tone-bad', 'The check, the fix or the verification did not hold.', 'Ari shows the error and delivers nothing.'],
];

export default function HomePage() {
  return (
    <div className="mk home-deep">
      <section className="hero-full mk-hero pb-16 pt-24 md:pt-24" aria-labelledby="hero-title">
        <div className="mk-wrap">
          <p className="mk-kicker"><b>Ari</b> · code review and security validation for teams shipping with AI agents</p>
          <h1 id="hero-title" className="mk-display mt-6">Ship fast.<br /><span className="dim">Know what you shipped.</span></h1>
          <div className="mt-6 flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <p className="mk-lede">Code now changes faster than anyone can read it. Ari reviews each change in the context of your repository, tests security hypotheses inside a sandbox you approve, and proposes fixes that count only when independent tests agree.</p>
            <div className="flex flex-wrap gap-3">
              <Link href={START.href} className="mk-btn mk-btn-primary">{START.label}<span aria-hidden="true" className="arrow">→</span></Link>
              <a href="#how" className="mk-btn mk-btn-secondary">How it works</a>
            </div>
          </div>
          <SignalField />
        </div>
      </section>

      <div className="hero-cover">
        {!DEMO_ONLY && <div className="mk-wrap"><OptionalUserBar /></div>}

        <section id="how" className="mk-section" aria-labelledby="how-title">
          <div className="mk-wrap">
            <div className="mk-reveal grid gap-6 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)] lg:items-end">
              <div>
                <p className="mk-kicker">How it works</p>
                <h2 id="how-title" className="mk-h2 mt-4">A reviewer and seven agents.<br /><span className="text-faint">Each with a narrow job.</span></h2>
              </div>
              <p className="mk-lede max-w-md text-base">Every agent is its own tool loop with its own permissions, coordinated by a deterministic state machine. Only three ever execute code, and never outside a sandbox.</p>
            </div>
            <div className="mk-agents">
              {BANDS.map((band, bi) => (
                <div key={band.title} className="mk-band mk-reveal">
                  <div className="mk-band-head"><h3>{band.title}</h3><p>{band.body}</p></div>
                  <div className="mk-band-rows">
                    {bi === 0 && <div className="mk-agent mk-agent-head" aria-hidden="true"><span>Agent</span><span>What it does</span><span>Runs code</span><span>Writes code</span></div>}
                    {band.agents.map(a => (
                      <div key={a.name} className="mk-agent">
                        <b>{a.name}</b>
                        <p>{a.does}</p>
                        <span className="k" data-on={a.on?.[0] || undefined}><span className="sr-only">Runs code: </span>{a.runs}</span>
                        <span className="k" data-on={a.on?.[1] || undefined}><span className="sr-only">Writes code: </span>{a.writes}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="mk-section mk-paper" aria-labelledby="states-title" data-nav-surface="light">
          <div className="mk-wrap">
            <div className="mk-reveal max-w-3xl">
              <p className="mk-kicker">Six states, never one green tick</p>
              <h2 id="states-title" className="mk-h2 mt-4">A finding says how far it got.</h2>
              <p className="mk-lede mt-5">Ari keeps a suspicion, an executed check and a verified repair visibly apart. Most findings stop early, and the console tells you where.</p>
            </div>
            <div className="mk-sample">
              <figure className="mk-window mk-reveal" aria-label="Sample finding">
                <div className="mk-window-bar">
                  <strong>acme/payments-lite</strong><span>2e24b60</span><span>payments: load payment by id</span>
                  <span className="mk-chip tone-ok ml-auto">Verified</span>
                </div>
                <pre className="mk-code" aria-label="Proposed fix diff">
                  <span><i>41</i>  def load(payment_id: str, user: User) -&gt; Payment:</span>
                  <span className="del"><i>42</i>-     row = db.payments.by_id(payment_id)</span>
                  <span className="add"><i>42</i>+     row = db.payments.by_id(payment_id, owner_id=user.id)</span>
                  <span><i>43</i>      if row is None:</span>
                  <span><i>44</i>          raise NotFound(&quot;payment&quot;)</span>
                </pre>
                <div className="mk-evidence">
                  <div><span className="mk-chip tone-signal">Flagged</span><span>Trace: any signed-in user reaches payments.load with another user&apos;s id.</span></div>
                  <div><span className="mk-chip tone-bad">Validated</span><span>Probe, sandbox: Bob read Alice&apos;s payment. Reproduced twice.</span></div>
                  <div><span className="mk-chip tone-ok">Verified</span><span>Verify, fresh checkout: the same request now returns 404; the suite passes.</span></div>
                </div>
                <figcaption className="px-4 py-3 font-mono text-[10px] uppercase tracking-[0.06em] text-faint">Sample finding · Ari&apos;s payments-lite example target</figcaption>
              </figure>
              <div className="mk-states mk-reveal" role="list">
                {STATES.map(([label, tone, what, then]) => (
                  <div key={label} className="mk-state" role="listitem">
                    <span className={`mk-chip ${tone}`}>{label}</span>
                    <p><b>{what}</b> {then}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section id="control" className="mk-section" aria-labelledby="control-title">
          <div className="mk-wrap">
            <div className="mk-reveal max-w-3xl">
              <p className="mk-kicker">Control and trust</p>
              <h2 id="control-title" className="mk-h2 mt-4">You decide what runs,<br /><span className="text-faint">and what reaches your code.</span></h2>
            </div>
            <div className="mk-grid2">
              <div className="mk-reveal">
                <p className="mk-list-title">How fixes reach you</p>
                <dl className="mk-list">
                  <div><dt>Open a pull request<small>Default</small></dt><dd>Each verified fix arrives as a PR. You review and merge.</dd></div>
                  <div><dt>Ask me first</dt><dd>Nothing is pushed until you approve each fix in Ari.</dd></div>
                  <div><dt>Commit to the default branch</dt><dd>Off unless an owner turns it on and confirms it. Ari never enables it for you.</dd></div>
                  <div><dt>Automatic reviews</dt><dd>Off for every repository until you turn them on. During the pilot you start each review.</dd></div>
                </dl>
              </div>
              <div className="mk-reveal">
                <p className="mk-list-title">What the GitHub App can do</p>
                <dl className="mk-list">
                  <div><dt>Contents<small>Read and write</small></dt><dd>Read the commit under review; push fix branches for pull requests.</dd></div>
                  <div><dt>Pull requests<small>Read and write</small></dt><dd>Comment on reviews you enabled and open fix pull requests.</dd></div>
                  <div><dt>Metadata<small>Read</small></dt><dd>List the repositories you installed Ari on.</dd></div>
                  <div><dt>Security checks</dt><dd>Run only against a copy Ari builds itself, never your live site, under an authorization a human approves. It expires after 7 days.</dd></div>
                  <div><dt>Revoking access</dt><dd>Uninstall the Ari app from GitHub settings at any time; Ari loses access immediately.</dd></div>
                </dl>
              </div>
            </div>
          </div>
        </section>

        <section className="mk-section mk-cta" aria-labelledby="cta-title">
          <div className="mk-wrap mk-reveal">
            <p className="mk-kicker">Private pilot</p>
            <h2 id="cta-title" className="mk-display mt-5">Point Ari at one repository.<br /><span className="dim">See what it can prove.</span></h2>
            <div className="mt-10 flex flex-wrap gap-3">
              <Link href={START.href} className="mk-btn mk-btn-primary">{START.label}<span aria-hidden="true" className="arrow">→</span></Link>
              <Link href="/pricing" className="mk-btn mk-btn-secondary">Pilot access</Link>
            </div>
          </div>
        </section>

        <LandingFooter />
      </div>
    </div>
  );
}
