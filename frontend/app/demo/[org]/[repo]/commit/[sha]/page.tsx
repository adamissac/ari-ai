'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useMemo, useState } from 'react';
import { DefenseMap, type MapState } from '@/components/defense-map';
import { Avatar, CiBadge, DemoBar, DemoDiff, VerdictChip } from '@/components/demo/ui';
import { Empty } from '@/components/ui';
import { DEMO_ORGS, findCommit, findRepo, relativeTime, type DemoCommit, type DemoRepo } from '@/lib/demo/data';
import { useDemoGate } from '@/lib/demo/gate';
import { useReplay } from '@/lib/demo/replay';
import { AGENT_ORDER, analyze, type AgentId, type AgentRunView, type Analysis } from '@/lib/demo/scenarios';

/** Ticks spent on code understanding and on the review before the security agents start. */
const UNDERSTAND_TICKS = 2;
const REVIEW_TICKS = 3;

type Status = 'queued' | 'running' | 'done' | 'skipped';
type Tab = 'overview' | 'review' | 'agents' | 'defense';
const TABS: { id: Tab; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'review', label: 'Code review' },
  { id: 'agents', label: 'Seven agents' },
  { id: 'defense', label: 'Defense Lab' },
];

interface Timeline {
  total: number;
  reviewStart: number;
  agentsStart: number;
  spans: Record<AgentId, { start: number; end: number }>;
}

function timeline(analysis: Analysis): Timeline {
  let cursor = UNDERSTAND_TICKS + REVIEW_TICKS;
  const spans = {} as Timeline['spans'];
  for (const agent of analysis.agents) {
    spans[agent.agent] = { start: cursor, end: cursor + agent.steps.length };
    cursor += agent.steps.length;
  }
  return { total: cursor, reviewStart: UNDERSTAND_TICKS, agentsStart: UNDERSTAND_TICKS + REVIEW_TICKS, spans };
}

function agentStatus(agent: AgentRunView, t: Timeline, position: number): Status {
  const span = t.spans[agent.agent];
  if (position < span.start) return 'queued';
  if (agent.status === 'skipped') return 'skipped';
  return position >= span.end ? 'done' : 'running';
}

export default function DemoCommitPage() {
  const { org, repo: name, sha } = useParams<{ org: string; repo: string; sha: string }>();
  const session = useDemoGate();
  const repo = findRepo(org, name);
  const commit = repo ? findCommit(repo, sha) : undefined;
  if (!session.user) return <div className="min-h-[60vh]" />;
  if (!repo || !commit) return <Empty>Commit not found.</Empty>;
  const orgName = DEMO_ORGS.find(o => o.login === org)?.name ?? org;
  return (
    <div data-testid="demo-commit">
      <DemoBar
        crumbs={[{ href: '/demo', label: 'Organizations' }, { href: `/demo/${org}`, label: orgName }, { href: `/demo/${org}/${repo.name}`, label: repo.name }, { label: commit.sha.slice(0, 7) }]}
        user={session.user}
        onSignOut={session.signOut}
      />
      <CommitAnalysis key={commit.sha} repo={repo} commit={commit} />
    </div>
  );
}

function CommitAnalysis({ repo, commit }: { repo: DemoRepo; commit: DemoCommit }) {
  const analysis = useMemo(() => analyze(repo, commit), [repo, commit]);
  const t = useMemo(() => timeline(analysis), [analysis]);
  const replay = useReplay(t.total);
  const [tab, setTab] = useState<Tab>('overview');
  const statuses = Object.fromEntries(analysis.agents.map(a => [a.agent, agentStatus(a, t, replay.position)])) as Record<AgentId, Status>;
  const ran = analysis.agents.filter(a => a.status === 'done' && statuses[a.agent] === 'done').length;
  const pct = Math.round((Math.min(replay.position, t.total) / t.total) * 100);

  return (
    <>
      <header className="demo-ink rounded-3xl px-6 pb-6 pt-7 md:px-9">
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div className="min-w-0 max-w-3xl">
            <p className="label-mono flex flex-wrap items-center gap-2 text-white/60">
              <span>{repo.org} / {repo.name}</span><span aria-hidden="true">·</span><span className="font-mono normal-case">{commit.sha.slice(0, 12)}</span>
            </p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight md:text-3xl" data-testid="demo-commit-message">{commit.message}</h1>
            {commit.body && <p className="mt-2 text-sm text-white/70">{commit.body}</p>}
            <p className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-white/70">
              <span className="flex items-center gap-2"><Avatar login={commit.author} size={20} /><span className="font-semibold text-white">{commit.author}</span></span>
              <span suppressHydrationWarning>pushed {relativeTime(commit.minutesAgo)}</span>
              <span className="rounded bg-white/10 px-1.5 py-0.5 font-mono">{commit.branch}</span>
              <span><span className="text-[#7fe0aa]">+{commit.additions}</span> <span className="text-[#ff9b88]">−{commit.deletions}</span></span>
              <CiBadge state={commit.ci} />
            </p>
          </div>
          <div className="flex min-w-[15rem] flex-col items-start gap-2 md:items-end">
            {replay.done ? <VerdictChip verdict={commit.verdict} /> : <span className="demo-chip demo-chip-info" data-testid="demo-analyzing">Analyzing · {pct}%</span>}
            <div className="flex gap-2">
              {!replay.done && <button type="button" onClick={replay.skip} className="rounded-md bg-white/10 px-3 py-1.5 text-xs text-white transition-colors hover:bg-white/20" data-testid="demo-skip">Skip to result</button>}
              {replay.done && <button type="button" onClick={replay.restart} className="rounded-md bg-white/10 px-3 py-1.5 text-xs text-white transition-colors hover:bg-white/20" data-testid="demo-replay">↺ Replay analysis</button>}
            </div>
          </div>
        </div>
        <div className="demo-progress mt-6" role="progressbar" aria-label="Analysis progress" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${pct}%` }} /></div>
        <dl className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Stat label="Duration" value={replay.done ? `${Math.floor(analysis.seconds / 60)}m ${analysis.seconds % 60}s` : '—'} />
          <Stat label="Agents run" value={`${ran} / 7`} />
          <Stat label="Findings" value={replay.done ? String(analysis.findings.length) : '—'} />
          <Stat label="Model cost" value={replay.done ? `$${analysis.usd.toFixed(2)}` : '—'} />
        </dl>
        <div role="tablist" aria-label="Commit analysis" className="demo-tabs mt-6">
          {TABS.map(item => (
            <button key={item.id} type="button" role="tab" aria-selected={tab === item.id} aria-controls={`panel-${item.id}`} id={`tab-${item.id}`} onClick={() => setTab(item.id)} className="demo-tab" data-testid={`demo-tab-${item.id}`}>
              <span>{item.label}</span>
            </button>
          ))}
        </div>
      </header>

      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} className="mt-6">
        {tab === 'overview' && <Overview analysis={analysis} t={t} position={replay.position} done={replay.done} statuses={statuses} commit={commit} onOpen={setTab} />}
        {tab === 'review' && <Review analysis={analysis} reviewed={replay.position >= t.agentsStart} />}
        {tab === 'agents' && <Agents analysis={analysis} t={t} position={replay.position} statuses={statuses} />}
        {tab === 'defense' && <Defense repo={repo} analysis={analysis} done={replay.done} />}
      </div>
    </>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return <div><dt className="label-mono text-white/50">{label}</dt><dd className="mt-1 font-display text-xl font-semibold tabular-nums">{value}</dd></div>;
}

// ---------------------------------------------------------------- overview

function Overview({ analysis, t, position, done, statuses, commit, onOpen }: { analysis: Analysis; t: Timeline; position: number; done: boolean; statuses: Record<AgentId, Status>; commit: DemoCommit; onOpen: (tab: Tab) => void }) {
  const phase = (start: number, end: number): Status => (position >= end ? 'done' : position >= start ? 'running' : 'queued');
  const items: { label: string; sub: string; status: Status }[] = [
    { label: 'Understand', sub: 'Index the commit', status: phase(0, t.reviewStart) },
    { label: 'Review', sub: 'Check the intent', status: phase(t.reviewStart, t.agentsStart) },
    ...AGENT_ORDER.map(role => ({ label: role.label, sub: role.job, status: statuses[role.agent] })),
    { label: 'Monitor', sub: 'Watch 24/7', status: done ? 'running' as Status : 'queued' as Status },
  ];
  const fixed = commit.verdict === 'fixed';
  return (
    <div className="flex flex-col gap-5">
      <section className="demo-panel p-5" aria-label="Pipeline">
        <p className="label-mono mb-3 text-white/55">Pipeline for this commit</p>
        <ol className="demo-pipe">
          {items.map(item => (
            <li key={item.label} className="demo-pipe-item" data-status={item.status}>
              <p className="text-sm font-semibold">{item.label}</p>
              <p className="mt-0.5 text-xs text-white/55">{item.sub}</p>
              <p className="label-mono mt-2 text-white/70">{STATUS_WORD[item.status]}</p>
            </li>
          ))}
        </ol>
      </section>
      {!done ? (
        <section className="rounded-2xl border border-line bg-white p-6" aria-live="polite">
          <p className="label-mono text-brand">In progress</p>
          <p className="mt-2 text-lg font-semibold tracking-tight">{currentActivity(analysis, t, position)}</p>
          <p className="mt-1 text-sm text-muted">Open <button type="button" className="text-brand underline-offset-2 hover:underline" onClick={() => onOpen('agents')}>Seven agents</button> to watch each step as it runs.</p>
        </section>
      ) : (
        <section className="grid gap-4 lg:grid-cols-[1.4fr_1fr]" data-testid="demo-result">
          <div className="rounded-2xl border border-line bg-white p-6">
            <p className="label-mono text-brand">Result</p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight">{analysis.headline}</h2>
            <p className="mt-2 text-sm leading-relaxed text-muted">{analysis.summary}</p>
            {analysis.findings.map(f => (
              <div key={f.id} className="mt-4 rounded-xl border border-line bg-panel-2 p-4">
                <p className="flex flex-wrap items-center gap-2 text-sm">
                  <span className={`demo-chip ${f.severity === 'critical' || f.severity === 'high' ? 'demo-chip-bad' : 'demo-chip-warn'}`}>{f.severity}</span>
                  <span className="demo-chip demo-chip-info">{f.kind}</span>
                  <span className="font-semibold">{f.title}</span>
                </p>
                <p className="mt-2 font-mono text-xs text-muted">{f.where}</p>
                <p className="mt-1 text-xs text-muted">{f.cwe}{f.cvss !== '—' ? ` · CVSS 3.1 ${f.cvss}` : ''} · {fixed ? 'fix verified' : 'fix not yet accepted'}</p>
              </div>
            ))}
          </div>
          <div className="flex flex-col gap-4">
            <div className="rounded-2xl border border-line bg-white p-6">
              <p className="label-mono text-brand">What happens next</p>
              {analysis.patch ? (
                <>
                  <p className="mt-2 font-semibold">{fixed ? `Pull request #${parseInt(commit.sha.slice(0, 3), 16) % 400 + 100} opened with the verified fix` : 'Fix is waiting for a person'}</p>
                  <p className="mt-1 text-sm text-muted">{fixed ? 'Nothing was merged. A teammate reviews the pull request like any other.' : 'Verify could not accept the candidate fix yet. A reviewer needs to look at the failing check.'}</p>
                  <button type="button" onClick={() => onOpen('review')} className="mt-3 text-sm font-medium text-brand">See the fix →</button>
                </>
              ) : (
                <><p className="mt-2 font-semibold">Nothing to fix</p><p className="mt-1 text-sm text-muted">The commit stays under continuous watch like the rest of the repository.</p></>
              )}
            </div>
            <div className="rounded-2xl border border-line bg-white p-6">
              <p className="label-mono text-brand">Defense</p>
              <p className="mt-2 font-semibold">{analysis.defense.recommendation.action}: {analysis.defense.recommendation.target}</p>
              <p className="mt-1 text-sm text-muted">{analysis.defense.recommendation.why}</p>
              <button type="button" onClick={() => onOpen('defense')} className="mt-3 text-sm font-medium text-brand">Open Defense Lab →</button>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

const STATUS_WORD: Record<Status, string> = { queued: 'Queued', running: 'Running', done: 'Done', skipped: 'Skipped' };

function currentActivity(analysis: Analysis, t: Timeline, position: number): string {
  if (position < t.reviewStart) return 'Indexing the commit at its exact SHA…';
  if (position < t.agentsStart) return 'Reviewing the change against what the code is meant to do…';
  const agent = analysis.agents.find(a => position >= t.spans[a.agent].start && position < t.spans[a.agent].end);
  if (!agent) return 'Finishing up…';
  const step = agent.steps[position - t.spans[agent.agent].start];
  return `${agent.label} is running ${step?.tool ?? 'its next step'}…`;
}

// ---------------------------------------------------------------- code review

function Review({ analysis, reviewed }: { analysis: Analysis; reviewed: boolean }) {
  const r = analysis.review;
  if (!reviewed) return <section className="rounded-2xl border border-line bg-white p-6"><p className="label-mono text-brand">Code review</p><p className="mt-2 text-sm text-muted">The reviewer is still reading this change. Results appear here when it finishes.</p></section>;
  const repaired = analysis.findings.some(f => f.kind === 'functional');
  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_22rem]" data-testid="demo-review">
      <div className="flex min-w-0 flex-col gap-5">
        <section className="rounded-2xl border border-line bg-white p-6">
          <p className="label-mono text-brand">What this change is meant to do</p>
          <p className="mt-2 text-lg font-semibold tracking-tight">{r.intent}</p>
          <p className="mt-3 text-sm text-muted">{r.verdict}</p>
        </section>
        <section aria-label="Changed code">
          <p className="label-mono mb-2 text-faint">Changed code · {r.comments.length} review comment{r.comments.length === 1 ? '' : 's'}</p>
          <div className="flex flex-col gap-3">{r.diff.map(file => <DemoDiff key={file.path} file={file} comments={r.comments} />)}</div>
        </section>
        {analysis.patch && (
          <section aria-label="Fix">
            <p className="label-mono mb-2 text-faint">{repaired ? 'Reviewer repair' : 'Candidate fix from Patch'} · {analysis.agents.find(a => a.agent === 'verify')?.outcome.startsWith('Accepted') ? 'accepted by Verify' : 'not yet accepted'}</p>
            <DemoDiff file={analysis.patch} label="fix" />
          </section>
        )}
      </div>
      <aside className="flex flex-col gap-5">
        <section className="rounded-2xl border border-line bg-white p-5">
          <p className="label-mono text-brand">Expected behaviour</p>
          <ul className="mt-3 flex flex-col gap-3">
            {r.expectations.map(e => (
              <li key={e.id} className="text-sm">
                <p className="font-medium">{e.text}</p>
                <p className="mt-0.5 text-xs text-faint">Learned from {e.source}</p>
              </li>
            ))}
          </ul>
        </section>
        <section className="rounded-2xl border border-line bg-white p-5">
          <p className="label-mono text-brand">Generated tests</p>
          <table className="mt-3 w-full text-xs">
            <thead><tr className="text-left text-faint"><th className="pb-2 font-normal">Test</th><th className="pb-2 font-normal">Before</th><th className="pb-2 font-normal">After fix</th></tr></thead>
            <tbody>
              {r.tests.map(test => (
                <tr key={test.name} className="border-t border-line align-top">
                  <td className="py-2 pr-2 font-mono [overflow-wrap:anywhere]">{test.name}</td>
                  <td className={`whitespace-nowrap py-2 pr-2 ${test.before === 'fail' ? 'text-bad' : 'text-ok'}`}>{test.before === 'fail' ? '✕ fail' : '✓ pass'}</td>
                  <td className="whitespace-nowrap py-2 text-ok">✓ pass</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-3 text-xs text-faint">A test that fails before the fix and passes after is what makes the fix count.</p>
        </section>
      </aside>
    </div>
  );
}

// ---------------------------------------------------------------- seven agents

function Agents({ analysis, t, position, statuses }: { analysis: Analysis; t: Timeline; position: number; statuses: Record<AgentId, Status> }) {
  const running = analysis.agents.find(a => statuses[a.agent] === 'running');
  const [picked, setPicked] = useState<AgentId | null>(null);
  const selected = analysis.agents.find(a => a.agent === (picked ?? running?.agent ?? 'scout'))!;
  const index = analysis.agents.indexOf(selected);
  const next = analysis.agents[index + 1];
  const status = statuses[selected.agent];
  const visible = status === 'done' || status === 'skipped' ? selected.steps.length : status === 'running' ? position - t.spans[selected.agent].start : 0;

  return (
    <div className="demo-panel grid gap-5 p-5 lg:grid-cols-[15rem_minmax(0,1fr)_16rem]" data-testid="demo-agents">
      <ol aria-label="Agents in orchestrator order" className="flex flex-col gap-1.5">
        {analysis.agents.map((agent, i) => (
          <li key={agent.agent}>
            <button type="button" aria-pressed={agent.agent === selected.agent} data-status={statuses[agent.agent]} onClick={() => setPicked(agent.agent)} className="demo-agent w-full" data-testid={`demo-agent-${agent.agent}`}>
              <span className="flex items-center gap-2.5">
                <span className="demo-agent-dot" aria-hidden="true" />
                <span className="font-mono text-xs text-white/40">{String(i + 1).padStart(2, '0')}</span>
                <span className="text-sm font-semibold">{agent.label}</span>
                <span className="ml-auto text-[0.68rem] text-white/50">{STATUS_WORD[statuses[agent.agent]]}</span>
              </span>
              <span className="mt-0.5 block pl-[42px] text-xs text-white/55">{agent.job}</span>
            </button>
          </li>
        ))}
      </ol>

      <section className="min-w-0" aria-live="polite">
        <p className="flex flex-wrap items-center gap-2">
          <span className="text-xl font-semibold tracking-tight">{selected.label}</span>
          <span className="demo-chip demo-chip-info">{selected.team} team</span>
          {status === 'done' && <span className="text-xs text-white/50">{selected.seconds}s · {selected.tokens.toLocaleString()} tokens</span>}
        </p>
        <p className="mt-3 text-base text-white/90" data-testid="demo-agent-outcome">
          {status === 'queued' ? 'Waiting for the previous agent to hand off.' : status === 'running' ? 'Working…' : selected.outcome}
        </p>
        {status === 'done' && selected.evidence.length > 0 && (
          <ul className="mt-4 flex flex-col gap-1.5">
            {selected.evidence.map(item => <li key={item} className="flex gap-2 text-sm text-white/75"><span aria-hidden="true" className="text-[#e0735c]">▸</span>{item}</li>)}
          </ul>
        )}
        {selected.steps.length > 0 && (
          <>
            <p className="label-mono mt-6 text-white/45">Steps · tool calls</p>
            <ol className="mt-3 flex flex-col gap-3" data-testid="demo-agent-steps">
              {selected.steps.slice(0, Math.max(0, visible) + (status === 'running' ? 1 : 0)).map((step, i) => {
                const live = status === 'running' && i === visible;
                return (
                  <li key={i} className="demo-step demo-rise" data-outcome={step.outcome} data-live={live || undefined}>
                    <span aria-hidden="true" className="demo-step-dot" />
                    <p className="flex flex-wrap items-baseline gap-x-2 text-sm">
                      <span className="font-mono text-[#ffb4a3]">{step.tool}</span>
                      <span className="text-white/60">{step.input}</span>
                    </p>
                    <p className={`mt-0.5 text-xs ${step.outcome === 'denied' ? 'text-[#ffc36b]' : 'text-white/55'}`}>
                      {live ? 'running…' : <>{step.outcome === 'denied' ? 'Blocked by policy — ' : '→ '}{step.result} · {step.ms >= 1000 ? `${(step.ms / 1000).toFixed(1)} s` : `${step.ms} ms`}</>}
                    </p>
                  </li>
                );
              })}
            </ol>
          </>
        )}
      </section>

      <aside className="flex flex-col gap-3 rounded-2xl bg-white/[0.03] p-4 shadow-[inset_0_0_0_1px_rgba(255,255,255,0.06)]">
        <p className="label-mono text-white/45">Handoff</p>
        <p className="text-sm text-white/85" data-testid="demo-agent-handoff">{status === 'done' || status === 'skipped' ? selected.handoff : 'Not yet — this agent has not finished.'}</p>
        {next && <p className="text-xs text-white/50">Next: <span className="text-white/75">{next.label}</span> — {next.job.toLowerCase()}.</p>}
        <p className="mt-auto border-t border-white/10 pt-3 text-xs text-white/45">Every tool call runs under a deterministic policy: sandbox-only network, read-only payloads, no pushes or merges.</p>
      </aside>
    </div>
  );
}

// ---------------------------------------------------------------- defense

function Defense({ repo, analysis, done }: { repo: DemoRepo; analysis: Analysis; done: boolean }) {
  const d = analysis.defense;
  const states: Record<string, MapState> = done ? d.watch : Object.fromEntries(repo.components.map((c, i) => [c.id, i === 1 ? 'checking' : 'healthy']));
  const r = d.recommendation;
  return (
    <div className="flex flex-col gap-5" data-testid="demo-defense">
      <DefenseMap
        nodes={repo.components}
        links={repo.links}
        states={states}
        checkedMinutesAgo={d.checkedMinutesAgo}
        title={`${repo.name} · continuous defense`}
        footnote="Simulated demo. In the product, “Being checked” appears only while a real check runs and “Healthy” only from a recorded result."
      />
      <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
        <section className="demo-panel p-6">
          <p className="label-mono text-white/50">Defense policy recommends</p>
          <p className="mt-2 text-2xl font-semibold tracking-tight">{r.action}</p>
          <p className="mt-0.5 text-sm text-white/70">on <span className="text-white">{r.target}</span></p>
          <p className="mt-3 text-sm text-white/75">{r.why}</p>
          <div className="mt-4">
            <p className="flex justify-between text-xs text-white/55"><span>Policy confidence</span><span className="font-mono">{Math.round(r.confidence * 100)}%</span></p>
            <div className="demo-progress mt-1.5"><span style={{ width: `${r.confidence * 100}%` }} /></div>
          </div>
          <p className="mt-4 text-xs text-white/50">A recommendation for a person. The policy never isolates or rate-limits a production service on its own.</p>
        </section>
        <section className="rounded-2xl border border-line bg-white p-6">
          <p className="label-mono text-brand">Activity</p>
          <ol className="mt-3 flex flex-col gap-3">
            {d.events.map((event, i) => (
              <li key={i} className="flex gap-3 text-sm">
                <span className="min-w-0"><span className="block">{event.text}</span><span className="text-xs text-faint" suppressHydrationWarning>{relativeTime(event.minutesAgo)}</span></span>
              </li>
            ))}
          </ol>
          <Link href="/lab" className="mt-5 inline-block text-sm font-medium text-brand">How the defense policy was trained and evaluated →</Link>
          <p className="mt-1 text-xs text-faint">The Defense Lab shows the real held-out evaluation of the policy behind these recommendations.</p>
        </section>
      </div>
    </div>
  );
}
