'use client';

import type { AgentName, AgentRun, AssessmentDetail } from '@hackatl/frontend-transport';
import { useMemo, useState, type ReactNode } from 'react';
import { ApprovalGate } from '@/components/assessment-approval-gate';
import { fullEventLog } from '@/lib/journey';
import { ErrorState, Loading } from '@/components/ui';
import { api } from '@/lib/api';
import { AGENT_ORDER } from '@/lib/demo/scenarios';
import { SPEEDS, useReplay } from '@/lib/demo/replay';
import { agentRunSummary, AGENT_RUN_STATUS, providerLabel, ASSESSMENT_STATE } from '@/lib/status';
import { useResource } from '@/lib/use-resource';

/** A run may only be rendered inside the repository and exact commit that created it. */
export function belongsToCommit(detail: AssessmentDetail, repoId: string, sha: string): boolean {
  return detail.assessment.repo_id === repoId && detail.assessment.commit_sha === sha;
}

export function CommitRunWorkspace({ assessmentId, repoId, sha, fullName, quickRead }: {
  assessmentId: string | null; repoId: string | null; sha: string; fullName: string; quickRead?: ReactNode;
}) {
  const [tab, setTab] = useState<'review' | 'agents'>('review');
  const run = useResource(assessmentId ? `commit-run:${repoId}:${sha}:${assessmentId}` : null,
    signal => api().assessment(assessmentId!, { signal }), 5000);
  const matching = run.status === 'ready' && repoId && belongsToCommit(run.data, repoId, sha) ? run.data : null;
  const detail = matching ? { ...matching, agent_runs: matching.agent_runs.filter(r => r.assessment_id === matching.assessment.id), findings: matching.findings.filter(f => f.assessment_id === matching.assessment.id && f.commit_sha === sha) } : null;
  const mismatch = run.status === 'ready' && !detail;
  return <>
    {detail?.assessment.state === 'AWAITING_APPROVAL' && <CommitApproval assessmentId={detail.assessment.id} projectId={detail.assessment.project_id} onDecided={run.reload} />}
    <div role="tablist" aria-label="Commit analysis" className="demo-tabs mt-6">
      {(['review', 'agents'] as const).map(key => <button type="button" role="tab" key={key} id={`commit-tab-${key}`} aria-controls="commit-work-panel" aria-selected={tab === key} className="demo-tab" onClick={() => setTab(key)}>{key === 'review' ? 'Code review' : '7 agents'}</button>)}
    </div>
    <div role="tabpanel" id="commit-work-panel" aria-labelledby={`commit-tab-${tab}`} className="mt-6">
      {assessmentId && run.status === 'loading' && <Loading label="Loading this commit’s run" />}
      {run.status === 'error' && <ErrorState error={run.error} onRetry={run.reload} />}
      {run.refreshError !== undefined && <p role="status">Could not refresh. Showing the last loaded records.</p>}
      {mismatch && <p role="alert">This run belongs to another repository or commit. Its records are not shown here.</p>}
      {!mismatch && tab === 'review' && <section className="glass p-6" data-testid="commit-reviewer">
        <p className="label-mono text-white/55">Code reviewer</p>
        <h2 className="mt-3 text-xl font-semibold">{detail ? agentRunSummary(detail.agent_runs.filter(r => r.agent === 'reviewer')) : 'Review this change.'}</h2>
        {!detail && <p className="mt-3 text-sm text-white/65">Start an authorized run above to record the reviewer’s work for this commit.</p>}
        {detail && <WorkerEvidence runs={detail.agent_runs.filter(r => r.agent === 'reviewer')} />}
        {detail?.findings.filter(f => f.kind === 'functional').map(f => <article className="mt-4 border-t border-white/10 pt-4" key={f.id}><h3>{f.title}</h3><p className="mt-1 text-sm text-white/60">{f.status}</p></article>)}
        {quickRead}
      </section>}
      {!mismatch && tab === 'agents' && <RecordedAgentMap key={assessmentId ?? 'not-run'} detail={detail} sha={sha} fullName={fullName} />}
    </div>
  </>;
}

function RecordedAgentMap({ detail, sha, fullName }: { detail: AssessmentDetail | null; sha: string; fullName: string }) {
  const runs = useMemo(() => detail?.agent_runs.filter(r => r.agent !== 'reviewer') ?? [], [detail]);
  const steps = useMemo(() => [...runs].sort((a, b) => Date.parse(a.started_at) - Date.parse(b.started_at)).flatMap(run => run.tool_calls.map(call => ({ run, call }))), [runs]);
  const replay = useReplay(steps.length, 900);
  const [selected, setSelected] = useState<AgentName | null>(null);
  const current = steps[Math.min(replay.position, Math.max(0, steps.length - 1))];
  const active = selected ?? current?.run.agent ?? 'scout';
  const worker = AGENT_ORDER.find(a => a.agent === active)!;
  const mine = runs.filter(r => r.agent === active);
  return <section className="amap commit-recorded-workspace" data-testid="commit-agent-map" aria-label="Seven agents at work">
    <header className="amap-head"><p className="amap-now">{detail ? `Recorded run · ${ASSESSMENT_STATE[detail.assessment.state].label}` : 'No recorded run for this commit'}</p><p className="text-xs text-white/55">Playback shows saved tool calls. It does not run agents.</p></header>
    <div className="amap-grid">
      <nav className="amap-rail" aria-label="Security agents">
        {(['Red', 'Blue', 'Independent'] as const).map(team => <div className="amap-group" key={team}><p className="amap-group-label">{team === 'Independent' ? 'Independent verification' : `${team} team`}</p><ol>
          {AGENT_ORDER.filter(a => a.team === team).map(a => {
            const latest = runs.filter(r => r.agent === a.agent).at(-1);
            return <li key={a.agent}><button type="button" className="amap-agent" aria-pressed={active === a.agent} onClick={() => setSelected(a.agent)}><span className="min-w-0 flex-1"><span className="amap-agent-name">{a.label}</span><span className="block text-xs text-white/50">{latest ? AGENT_RUN_STATUS[latest.status].label : 'Not run'}</span></span></button></li>;
          })}
        </ol></div>)}
      </nav>
      <div className="amap-stage">
        <div className="commit-recording-map">
          <p className="label-mono text-white/50">{fullName}</p>
          <div className="commit-recording-node"><span className="label-mono">Selected commit</span><strong>{sha.slice(0, 7)}</strong></div>
          <span className="commit-recording-connector" aria-hidden="true" />
          <div className="commit-recording-worker"><span className="label-mono text-white/50">{selected ? 'Selected agent' : 'Replay position'}</span><h3>{worker.label}</h3><p>{current && !selected ? current.call.tool_name : worker.job}</p></div>
        </div>
        <div className="amap-transport">
          <button type="button" className="amap-play" disabled={!steps.length} aria-label={replay.playing ? 'Pause replay' : 'Play replay'} onClick={replay.toggle}>{replay.playing ? 'Ⅱ' : '▶'}</button>
          <input className="min-w-0 flex-1" aria-label="Replay position" type="range" min={0} max={steps.length || 1} value={replay.position} disabled={!steps.length} onChange={e => { setSelected(null); replay.seek(Number(e.target.value)); }} />
          <button type="button" className="amap-speed" aria-label="Replay speed" onClick={() => replay.setSpeed(SPEEDS[(SPEEDS.indexOf(replay.speed) + 1) % SPEEDS.length]!)}>{replay.speed}×</button>
          <button type="button" className="amap-speed" disabled={!steps.length} onClick={replay.skip}>End</button>
          <span className="text-xs text-white/55">{replay.position}/{steps.length}</span>
        </div>
      </div>
      <aside className="amap-inspect"><p className="label-mono text-white/50">{worker.team}</p><h2 className="mt-2 text-xl font-semibold">{worker.label}</h2><p className="mt-2 text-sm text-white/65">{agentRunSummary(mine)}</p>
        {!mine.length && <p className="mt-4 text-sm text-white/55">No work has been recorded for this agent on this commit.</p>}
        <WorkerEvidence runs={mine} />
        {selected && <button type="button" className="amap-follow" onClick={() => setSelected(null)}>Follow replay</button>}
      </aside>
    </div>
    {!!detail?.findings.filter(f => f.kind === 'security').length && <details className="border-t border-white/10 p-5"><summary>Security findings for this commit</summary>{detail.findings.filter(f => f.kind === 'security').map(f => <p className="mt-3 text-sm" key={f.id}>{f.title} · {f.status}</p>)}</details>}
  </section>;
}

function WorkerEvidence({ runs }: { runs: AgentRun[] }) {
  return <>{runs.map(run => <div key={run.id} className="mt-4 text-sm">
    <p className="text-white/55">{AGENT_RUN_STATUS[run.status].label} · {providerLabel(run.provider_mode).label}</p>
    {run.error && <p role="alert" className="mt-2">{run.error.message}</p>}
    <details className="mt-3"><summary>Recorded tool calls ({run.tool_calls.length})</summary><ol className="mt-2 space-y-2">{run.tool_calls.map((call, i) => <li key={i} className="break-words text-xs text-white/65">{call.tool_name} · {call.outcome}{call.error_code ? ` · ${call.error_code}` : ''}</li>)}</ol></details>
  </div>)}</>;
}

function CommitApproval({ assessmentId, projectId, onDecided }: { assessmentId: string; projectId: string; onDecided: () => void }) {
  const events = useResource(`commit-approval:${assessmentId}`, signal => fullEventLog(after => api().eventsLog(assessmentId, after, { signal })), 5000);
  if (events.status === 'loading') return <Loading label="Loading this run’s approval request" />;
  if (events.status === 'error') return <ErrorState error={events.error} onRetry={events.reload} />;
  if (events.data.truncated) return <p role="alert">The run’s approval log is incomplete. Reload to check the approval request.</p>;
  return <ApprovalGate projectId={projectId} events={events.data.items} onDecided={onDecided} />;
}
