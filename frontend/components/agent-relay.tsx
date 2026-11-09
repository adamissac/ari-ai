'use client';

import type { AgentName } from '@hackatl/frontend-transport';
import type { FindingFacts, RelayItem, RelayStatus, RelayTile } from '@/lib/relay';
import { relaySummary } from '@/lib/relay';
import { Term } from '@/components/term';

/** Status reads as a small mark and a word; the row itself stays calm. */
const STATUS_MARK: Record<RelayStatus, string> = { done: 'done', running: 'running', queued: 'queued', failed: 'failed', cancelled: 'queued', not_run: 'idle', not_needed: 'idle', not_reached: 'idle' };
const IDLE_STATUSES: ReadonlySet<RelayStatus> = new Set(['not_run', 'not_needed', 'not_reached']);
const GROUPS: readonly { key: string; label: string; question: string; agents: readonly AgentName[] }[] = [
  { key: 'review', label: 'Review', question: 'Does the change work?', agents: ['reviewer'] },
  { key: 'security', label: 'Security', question: 'Can someone break it?', agents: ['scout', 'probe', 'trace', 'diagnose'] },
  { key: 'proof', label: 'Fix & proof', question: 'Did the fix hold up?', agents: ['patch', 'verify', 'fortify'] },
];

/**
 * The eight agents as a pipeline, in the order the orchestrator runs them, with
 * the human approval gate between planning and fixing. Selecting a row opens that
 * agent's recorded runs below.
 */
export function AgentRelay({
  items,
  selected,
  onSelect,
  findings,
  skipNote,
}: {
  items: RelayItem[];
  selected: AgentName;
  onSelect: (a: AgentName) => void;
  findings: FindingFacts[];
  skipNote?: string | null;
}) {
  const agents = items.filter((item): item is RelayTile => item.kind === 'agent');
  const numbers = new Map(agents.map((item, i) => [item.agent, i + 1]));
  const summary = relaySummary(items, findings);
  const gate = items.find(item => item.kind === 'gate');
  const hasSkippedStep = agents.some(item => item.status === 'not_needed');
  const renderGroup = (group: (typeof GROUPS)[number]) => {
    const groupItems = agents.filter(item => group.agents.includes(item.agent));
    return (
      <section className="pipeline-group" key={group.key} aria-labelledby={`pipeline-group-${group.key}`}>
        <header className="pipeline-group-heading">
          <h3 id={`pipeline-group-${group.key}`} className="label-mono">{group.label}</h3>
          <p>{group.question}</p>
        </header>
        <ol className="pipeline-list" aria-label={`${group.label} steps`}>
          {groupItems.map(item => {
            const n = numbers.get(item.agent) ?? 0;
            const idle = IDLE_STATUSES.has(item.status);
            const pressed = item.agent === selected;
            return (
              <li key={item.agent}>
                <button
                  type="button"
                  aria-pressed={pressed}
                  onClick={() => onSelect(item.agent)}
                  data-testid={`relay-${item.agent}`}
                  data-status={item.status}
                  className="pipeline-row"
                  title={item.job}
                >
                  <span className="pipeline-number" aria-hidden="true">{n}</span>
                  <span className="pipeline-agent">
                    <span className="pipeline-agent-name">{item.label}</span>
                    <span className="pipeline-job">{item.job}</span>
                  </span>
                  <span className="pipeline-result">{idle ? item.statusText : item.handoff}</span>
                  <span className="pipeline-status" data-mark={STATUS_MARK[item.status]}><span aria-hidden="true" className="relay-dot" />{item.statusText}</span>
                  <span className="pipeline-chevron" aria-hidden="true">›</span>
                </button>
              </li>
            );
          })}
        </ol>
      </section>
    );
  };

  return (
    <section className="pipeline" aria-labelledby="relay-title" data-testid="agent-relay">
      <header className="pipeline-header">
        <div className="pipeline-header-copy">
          <h2 id="relay-title">Review pipeline</h2>
          <p>One code reviewer and seven security agents run in order. A person must give <Term t="approval">approval</Term> before any fix is built.</p>
        </div>
        <p className="pipeline-progress">
          <strong>{summary.finished} of {summary.total} steps finished</strong>
          {summary.skipped > 0 && <span> · {summary.skipped} skipped</span>}
        </p>
      </header>
      <div className="pipeline-summary" data-testid="relay-summary">
        <div className="pipeline-stat"><strong>{summary.behaviour}</strong><span>Behaviour issues</span></div>
        <div className="pipeline-stat"><strong>{summary.suspicions}</strong><span>Security suspicions</span></div>
        <div className="pipeline-stat"><strong>{summary.confirmed}</strong><span>Confirmed by a test</span></div>
        <div className="pipeline-stat"><strong>{summary.fixesVerified}</strong><span>Fixes verified</span></div>
      </div>
      {skipNote && hasSkippedStep && (
        <p className="pipeline-skip-note" data-testid="relay-skip-note">
          <span aria-hidden="true" className="pipeline-skip-dot" />
          Run ended early: {skipNote}.
        </p>
      )}
      <div className="pipeline-groups">
        {renderGroup(GROUPS[0]!)}
        {renderGroup(GROUPS[1]!)}
        {gate?.kind === 'gate' && (
          <ol className="pipeline-gate-list" aria-label="Approval gate">
            <li className="pipeline-gate" data-testid="relay-gate" data-status={gate.status} title="Human approval">
              <span aria-hidden="true" className="relay-dot" />
              <span className="pipeline-gate-copy"><strong>Human approval</strong><span>{gate.text}</span></span>
            </li>
          </ol>
        )}
        {renderGroup(GROUPS[2]!)}
      </div>
    </section>
  );
}
