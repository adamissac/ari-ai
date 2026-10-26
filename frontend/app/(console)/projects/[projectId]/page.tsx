'use client';

import type { Finding, SeverityLevel } from '@hackatl/frontend-transport';
import Link from 'next/link';
import { PillarLoopSection, ProjectJourney } from '@/components/project-progress';
import { useProject } from '@/components/project';
import { Async, Badge, Empty, ErrorState, Loading, PageTitle, Panel } from '@/components/ui';
import { api } from '@/lib/api';
import { projectOverview } from '@/lib/overview';
import { findingsForRepo, repoAnalytics } from '@/lib/repo-analytics';
import { effectiveScopeStatus, FINDING_STATUS, SEVERITY } from '@/lib/status';
import { useResource } from '@/lib/use-resource';

export default function ProjectOverview() {
  const { project, selectedRepo } = useProject();
  const assessments = useResource(`asm:${project.id}`, signal => api().assessments(project.id, { signal }), 5000);
  const findings = useResource(`fnd:${project.id}`, signal => api().findings(project.id, { signal }), 10000);
  const scopes = useResource(`scopes:${project.id}`, signal => api().scopes(project.id, { signal }));
  const snapshots = useResource(
    selectedRepo ? `snapshots:${selectedRepo.id}` : null,
    signal => selectedRepo
      ? api().snapshots(selectedRepo.id, { limit: 100 }, { signal })
      : Promise.resolve({ items: [], next_cursor: null }),
  );

  return (
    <div className="flex min-w-0 flex-col gap-6">
      <PageTitle title="Analytics" subtitle={selectedRepo?.full_name ?? 'No repository connected'} />
      {!selectedRepo ? (
        <Empty>
          No repository is connected. <Link className="text-brand hover:underline" href={`/projects/${project.id}/settings#connect-repo`}>Connect a repository</Link>.
        </Empty>
      ) : (
        <Async resource={assessments} label="assessments">
          {assessmentPage => (
            <Async resource={findings} label="findings">
              {findingPage => (
                <Async resource={snapshots} label="saved snapshots">
                  {snapshotPage => {
                    const repoAssessments = assessmentPage.items.filter(assessment => assessment.repo_id === selectedRepo.id);
                    const repoFindings = findingsForRepo(
                      selectedRepo.id,
                      assessmentPage.items,
                      findingPage.items,
                      snapshotPage.items.map(snapshot => snapshot.id),
                    );
                    const analytics = repoAnalytics({
                      repoId: selectedRepo.id,
                      assessments: assessmentPage.items,
                      findings: findingPage.items,
                      snapshotIds: snapshotPage.items.map(snapshot => snapshot.id),
                      now: new Date(),
                    });
                    const activeScopeCount = scopes.status === 'ready'
                      ? scopes.data.items.filter(scope =>
                        effectiveScopeStatus(scope) === 'active'
                        && scope.targets.some(target => target.repo_id === selectedRepo.id),
                      ).length
                      : null;
                    const summary = projectOverview({
                      projectId: project.id,
                      repoCount: 1,
                      activeScopeCount,
                      monitoringEnabled: project.settings.monitoring_policy.enabled,
                      assessments: repoAssessments,
                      findings: repoFindings,
                    });
                    const stale = [assessments, findings, snapshots, scopes].some(resource => resource.refreshError !== undefined);
                    const truncated = assessmentPage.next_cursor !== null || findingPage.next_cursor !== null || snapshotPage.next_cursor !== null;
                    const summaryPath = summary.action.href.split('#')[0] ?? summary.action.href;
                    const summaryHash = summary.action.href.includes('#') ? `#${summary.action.href.split('#')[1]}` : '';
                    const summaryHref = `${summaryPath}${summaryPath.includes('?') ? '&' : '?'}repo=${encodeURIComponent(selectedRepo.id)}${summaryHash}`;

                    return (
                      <div className="flex min-w-0 flex-col gap-6">
                        <section aria-label="Project summary" className="min-w-0" data-testid="project-summary">
                          {scopes.status === 'loading' ? <Loading label="Loading project summary" /> : (
                            <>
                              <h2 className="text-xl font-semibold tracking-tight">{summary.headline}</h2>
                              <p className="mt-2 max-w-3xl text-sm text-muted">{summary.detail}</p>
                              {scopes.status === 'error' && <div className="mt-3"><ErrorState error={scopes.error} onRetry={scopes.reload} context="Scope status unavailable" /></div>}
                              {stale && <p role="status" className="mt-3 text-xs text-warn" data-testid="summary-stale">Could not refresh the latest records. The numbers above are from the last successful load and may be out of date.</p>}
                              <div className="mt-4"><Link href={summaryHref} className="inline-flex items-center rounded-lg bg-brand px-4 py-2 text-sm font-medium text-on-brand hover:bg-brand-deep">{summary.action.label}</Link></div>
                            </>
                          )}
                        </section>
                        {analytics.checksRun === 0 && (
                          <p className="text-sm">
                            <Link className="font-medium text-brand hover:underline" href={`/projects/${project.id}/setup?repo=${encodeURIComponent(selectedRepo.id)}`}>Run your first check →</Link>
                          </p>
                        )}
                        <Panel title="Repository activity">
                          <div data-testid="analytics-stats" className="grid grid-cols-2 divide-x divide-y divide-line sm:grid-cols-4 sm:divide-y-0">
                            <StatCell label="Commits checked" value={analytics.commitsChecked} />
                            <StatCell label="Checks run" value={analytics.checksRun} />
                            <StatCell label="Open findings" value={analytics.openFindings} />
                            <StatCell label="Fixes verified" value={analytics.fixesVerified} />
                          </div>
                        </Panel>
                        <p className="-mt-4 text-xs text-faint">
                          From Ari&apos;s saved records for {selectedRepo.full_name}
                          {truncated && <> · based on the latest {assessmentPage.items.length} checks and {findingPage.items.length} findings loaded</>}
                        </p>
                        <Panel title="Checks per day">
                          <ChecksChart days={analytics.checksPerDay} />
                        </Panel>
                        <div className="grid min-w-0 gap-6 lg:grid-cols-2">
                          <Panel title="Findings by severity">
                            <BreakdownRows
                              rows={(Object.keys(analytics.bySeverity) as (SeverityLevel | 'unassessed')[]).map(level => ({
                                label: level === 'unassessed' ? 'Unassessed' : SEVERITY[level].label,
                                value: analytics.bySeverity[level],
                                tone: level === 'critical' || level === 'high' ? 'var(--color-bad)'
                                  : level === 'medium' ? 'var(--color-warn)'
                                  : level === 'low' ? 'var(--color-info)'
                                  : 'var(--color-muted)',
                              }))}
                            />
                          </Panel>
                          <Panel title="Findings by status">
                            <BreakdownRows rows={[
                              { label: 'Open', value: analytics.byStatusGroup.open, tone: 'var(--color-bad)' },
                              { label: 'Fixed', value: analytics.byStatusGroup.fixed, tone: 'var(--color-ok)' },
                              { label: 'Closed', value: analytics.byStatusGroup.closed, tone: 'var(--color-muted)' },
                            ]} />
                          </Panel>
                        </div>
                        <Panel title="Typical check duration">
                          <p className="font-mono text-3xl font-semibold text-ink">{analytics.medianDurationMs === null ? '—' : durationLabel(analytics.medianDurationMs)}</p>
                          {analytics.medianDurationMs === null && <p className="mt-2 text-sm text-muted">No completed checks yet</p>}
                        </Panel>
                        <Panel title="Top open findings">
                          {analytics.topOpen.length === 0 ? <Empty>No open findings for this repository.</Empty> : (
                            <ul className="divide-y divide-line">
                              {analytics.topOpen.map(finding => <FindingRow key={finding.id} finding={finding} projectId={project.id} repoId={selectedRepo.id} />)}
                            </ul>
                          )}
                        </Panel>
                        <details className="project-detail">
                          <summary>Project progress</summary>
                          <PillarLoopSection
                            projectId={project.id}
                            repoCount={1}
                            activeScopeCount={activeScopeCount}
                            monitoringEnabled={project.settings.monitoring_policy.enabled}
                            assessmentCount={repoAssessments.length}
                            findings={repoFindings}
                          />
                          {activeScopeCount !== null && (
                            <ProjectJourney
                              projectId={project.id}
                              repoCount={1}
                              activeScopeCount={activeScopeCount}
                              monitoringEnabled={project.settings.monitoring_policy.enabled}
                              assessments={repoAssessments}
                              findingStatuses={repoFindings.map(finding => finding.status)}
                            />
                          )}
                        </details>
                      </div>
                    );
                  }}
                </Async>
              )}
            </Async>
          )}
        </Async>
      )}
    </div>
  );
}

function StatCell({ label, value }: { label: string; value: number }) {
  return (
    <div className="min-w-0 px-4 py-3 first:pl-0 last:pr-0">
      <p className="font-mono text-2xl font-semibold text-ink">{value.toLocaleString()}</p>
      <p className="mt-1 text-xs text-muted">{label}</p>
    </div>
  );
}

function ChecksChart({ days }: { days: { date: string; completed: number; active: number; failed: number }[] }) {
  const totals = days.map(day => day.completed + day.active + day.failed);
  const max = Math.max(1, ...totals);
  const completed = days.reduce((sum, day) => sum + day.completed, 0);
  const active = days.reduce((sum, day) => sum + day.active, 0);
  const failed = days.reduce((sum, day) => sum + day.failed, 0);
  const plotTop = 20;
  const baseline = 150;
  const plotHeight = baseline - plotTop;
  const xFor = (index: number) => 12 + index * 29;
  const labelIndexes = new Set([0, 5, 10, 15, 20, 25, days.length - 1]);
  return (
    <>
      <div className="min-w-0 overflow-x-auto">
        <svg
          className="block min-w-[700px] w-full"
          viewBox="0 0 900 190"
          role="img"
          aria-label={`30-day check activity: ${completed} completed, ${active} active, ${failed} failed.`}
        >
          {[0, 0.5, 1].map(fraction => {
            const y = baseline - fraction * plotHeight;
            return <line key={fraction} x1="0" x2="890" y1={y} y2={y} stroke="var(--color-line)" strokeWidth="1" />;
          })}
          <text x="2" y={plotTop - 5} fill="var(--color-faint)" fontSize="10">{max}</text>
          <text x="2" y={baseline + 4} fill="var(--color-faint)" fontSize="10">0</text>
          {days.map((day, index) => {
            const values = [
              { value: day.completed, color: 'var(--color-ok)' },
              { value: day.active, color: 'var(--color-warn)' },
              { value: day.failed, color: 'var(--color-bad)' },
            ];
            let offset = 0;
            const rectangles = values.map(({ value, color }, part) => {
              const height = value / max * plotHeight;
              const y = baseline - offset - height;
              offset += height;
              return value === 0 ? null : <rect key={part} x={xFor(index)} y={y} width="17" height={height} fill={color} />;
            });
            const label = new Date(`${day.date}T00:00:00Z`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' });
            return (
              <g key={day.date}>
                {rectangles}
                {labelIndexes.has(index) && <text x={xFor(index) + 8} y="177" textAnchor="middle" fill="var(--color-faint)" fontSize="9" fontFamily="monospace">{label}</text>}
              </g>
            );
          })}
        </svg>
      </div>
      <div aria-hidden="true" className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted">
        <ChartLegend label="Completed" color="var(--color-ok)" />
        <ChartLegend label="Active" color="var(--color-warn)" />
        <ChartLegend label="Failed" color="var(--color-bad)" />
      </div>
      <table className="sr-only">
        <caption>Check outcomes for the last 30 UTC days</caption>
        <thead><tr><th scope="col">Date</th><th scope="col">Completed</th><th scope="col">Active</th><th scope="col">Failed</th></tr></thead>
        <tbody>{days.map(day => <tr key={day.date}><th scope="row">{day.date}</th><td>{day.completed}</td><td>{day.active}</td><td>{day.failed}</td></tr>)}</tbody>
      </table>
    </>
  );
}

function ChartLegend({ label, color }: { label: string; color: string }) {
  return <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />{label}</span>;
}

function BreakdownRows({ rows }: { rows: { label: string; value: number; tone: string }[] }) {
  const max = Math.max(1, ...rows.map(row => row.value));
  return (
    <ul className="divide-y divide-line">
      {rows.map(row => (
        <li key={row.label} className="flex items-center gap-3 py-2.5 text-sm">
          <span className="w-24 shrink-0 text-muted">{row.label}</span>
          <span className="h-1.5 min-w-0 flex-1 bg-panel-2" role="meter" aria-label={`${row.label} findings`} aria-valuemin={0} aria-valuemax={max} aria-valuenow={row.value}>
            <span className="block h-full" style={{ width: `${row.value / max * 100}%`, backgroundColor: row.tone }} />
          </span>
          <span className="w-8 text-right font-mono text-ink">{row.value}</span>
        </li>
      ))}
    </ul>
  );
}

function FindingRow({ finding, projectId, repoId }: { finding: Finding; projectId: string; repoId: string }) {
  return (
    <li className="flex min-w-0 flex-wrap items-center justify-between gap-2 py-3">
      <Link className="min-w-0 flex-1 break-words text-sm hover:text-accent" href={`/projects/${projectId}/findings/${finding.id}?repo=${encodeURIComponent(repoId)}`}>{finding.title}</Link>
      <span className="flex flex-wrap items-center gap-2">
        {finding.severity ? <Badge view={SEVERITY[finding.severity.level]} /> : <span className="text-xs text-faint">unassessed</span>}
        <Badge view={FINDING_STATUS[finding.status]} />
      </span>
    </li>
  );
}

function durationLabel(durationMs: number): string {
  const totalSeconds = Math.floor(durationMs / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;
}
