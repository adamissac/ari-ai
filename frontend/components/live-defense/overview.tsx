'use client';

import type { DefenseRecommendation, Incident, MonitoringEvent, Project, ReassessmentRequest } from '@hackatl/frontend-transport';
import Link from 'next/link';
import { DefenseMap } from '@/components/defense-map';
import { DefenseSwitch } from '@/components/defense-switch';
import { SimulationCaveat, SourceTag } from '@/components/live-defense/common';
import { Async, Badge, Empty, Mono, Panel, Tag, Time } from '@/components/ui';
import { actionInWords, isOpenIncidentState, liveDefenseHref, liveDefenseOverviewCopy, MISSING_LIVE_APIS, USED_LIVE_APIS, type LiveDefenseMode } from '@/lib/live-defense';
import { PREVIEW_EVENTS, PREVIEW_INCIDENTS, PREVIEW_LINKS, PREVIEW_NODES, PREVIEW_RECOMMENDATIONS, PREVIEW_STATES } from '@/lib/live-defense-preview';
import { STATE_LABEL } from '@/lib/incidents';
import { EVENT_STATUS } from '@/lib/status';
import type { Resource } from '@/lib/use-resource';

export function LiveOverview({
  mode,
  projectId,
  project,
  reloadProject,
  events,
  incidents,
  recs,
  reassess,
}: {
  mode: LiveDefenseMode;
  projectId: string | null;
  project?: Project;
  reloadProject?: () => void;
  events?: Resource<{ items: MonitoringEvent[] }>;
  incidents?: Resource<{ items: Incident[] }>;
  recs?: Resource<{ items: DefenseRecommendation[]; label: string }>;
  reassess?: Resource<{ items: ReassessmentRequest[] }>;
}) {
  if (mode === 'layout-preview') return <PreviewOverview projectId={projectId} />;
  return (
    <LiveOverviewRecords
      projectId={projectId}
      project={project}
      reloadProject={reloadProject}
      events={events}
      incidents={incidents}
      recs={recs}
      reassess={reassess}
    />
  );
}

function LiveOverviewRecords({
  projectId, project, reloadProject, events, incidents, recs, reassess,
}: {
  projectId: string | null;
  project?: Project;
  reloadProject?: () => void;
  events?: Resource<{ items: MonitoringEvent[] }>;
  incidents?: Resource<{ items: Incident[] }>;
  recs?: Resource<{ items: DefenseRecommendation[]; label: string }>;
  reassess?: Resource<{ items: ReassessmentRequest[] }>;
}) {
  const eventItems = events?.status === 'ready' ? events.data.items : [];
  const incidentItems = incidents?.status === 'ready' ? incidents.data.items : [];
  const recItems = recs?.status === 'ready' ? recs.data.items : [];
  const open = incidentItems.filter(item => isOpenIncidentState(item.state));
  const copy = liveDefenseOverviewCopy({
    monitoringEnabled: project?.settings.monitoring_policy.enabled ?? false,
    eventsKnown: events?.status === 'ready',
    eventCount: eventItems.length,
    simulatedEventCount: eventItems.filter(item => item.simulated).length,
    incidentsKnown: incidents?.status === 'ready',
    openIncidentCount: open.length,
    simulatedIncidentCount: open.filter(item => item.simulated).length,
    recommendationsKnown: recs?.status === 'ready',
    recommendationCount: recItems.length,
  });
  return (
    <div className="flex flex-col gap-4">
      <p className="rounded-xl border border-line bg-panel p-5 text-sm text-ink" data-testid="live-defense-summary">{copy}</p>
      {project && reloadProject && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-line bg-panel px-5 py-4">
          <DefenseSwitch project={project} onChange={() => reloadProject()} />
          <p className="text-xs text-muted">Same owner-only switch as Monitoring. It turns repository re-checks on or off. It does not arm an enforcer.</p>
        </div>
      )}
      <ul className="ld-stat-row" aria-label="Recorded Live Defense counts">
        <li><span>Events</span> {events?.status === 'ready' ? eventItems.length : '…'}</li>
        <li><span>Open incidents</span> {incidents?.status === 'ready' ? open.length : '…'}</li>
        <li><span>Simulation recommendations</span> {recs?.status === 'ready' ? recItems.length : '…'}</li>
        <li><span>Re-checks</span> {reassess?.status === 'ready' ? reassess.data.items.length : '…'}</li>
      </ul>
      <Panel title="Component map">
        <Empty>
          No component-health API exists, so this page does not draw a live map or mark anything healthy.
          The <Link className="text-accent hover:underline" href="/lab">Defense Lab</Link> replays a recorded isolated-network evaluation.
          Open sample layout to review the map chrome against illustrative nodes.
        </Empty>
      </Panel>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Panel title="Recorded events" actions={<SourceTag mode="live" />}>
          {events ? (
            <Async resource={events} label="monitoring events">
              {page => page.items.length === 0 ? <Empty>No events received. Only signed GitHub deliveries or authenticated runtime batches appear here.</Empty> : (
                <ol className="flex flex-col gap-2">
                  {page.items.slice(0, 8).map(event => (
                    <li key={event.id} className="rounded-md border border-line bg-panel-2 p-2.5 text-sm">
                      <div className="flex flex-wrap items-center gap-2">
                        <Tag tone="accent">{event.source}</Tag>
                        <Tag>{event.type.replaceAll('_', ' ')}</Tag>
                        {event.simulated && <Tag tone="warn">replayed / fixture event</Tag>}
                        <Badge view={EVENT_STATUS[event.status]} />
                        <span className="text-xs text-muted">received <Time iso={event.received_at} /></span>
                      </div>
                    </li>
                  ))}
                </ol>
              )}
            </Async>
          ) : <Empty>Events were not requested.</Empty>}
        </Panel>
        <Panel title="Open incidents" actions={<Link className="text-xs text-accent hover:underline" href={liveDefenseHref(projectId, 'incidents')}>Investigate</Link>}>
          {incidents ? (
            <Async resource={incidents} label="incidents">
              {page => {
                const openItems = page.items.filter(item => isOpenIncidentState(item.state));
                if (openItems.length === 0) return <Empty>No open incidents.</Empty>;
                return (
                  <ul className="flex flex-col gap-2">
                    {openItems.slice(0, 6).map(item => (
                      <li key={item.id}>
                        <Link href={liveDefenseHref(projectId, 'incidents') + `/${item.id}`} className="block rounded-md border border-line bg-panel-2 p-2.5 text-sm hover:bg-white">
                          <span className="font-medium">{item.title}</span>
                          <span className="mt-1 flex flex-wrap gap-1 text-xs text-muted">
                            {item.simulated && <Tag tone="warn">Synthetic</Tag>}
                            <Tag>{STATE_LABEL[item.state]}</Tag>
                            opened <Time iso={item.opened_at} />
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                );
              }}
            </Async>
          ) : <Empty>Incidents were not requested.</Empty>}
        </Panel>
      </div>
      <Panel title="Simulation recommendations" actions={<Link className="text-xs text-accent hover:underline" href={liveDefenseHref(projectId, 'explain')}>Explainability</Link>}>
        <SimulationCaveat />
        {recs ? (
          <Async resource={recs} label="recommendations">
            {page => (
              <>
                <p className="my-2 text-xs text-faint">Backend label: {page.label}</p>
                {page.items.length === 0 ? <Empty>No recommendation has been requested for this project.</Empty> : (
                  <ul className="flex flex-col gap-2">
                    {page.items.slice(0, 5).map(rec => (
                      <li key={rec.id} className="rounded-md border border-line bg-panel-2 p-2.5 text-sm">
                        <p className="font-medium">{actionInWords(rec.action, rec.node)}</p>
                        <p className="mt-1 text-xs text-muted">policy <Mono>{rec.policy_version}</Mono></p>
                        <p className="mt-1 text-xs text-warn">{rec.caveat}</p>
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}
          </Async>
        ) : <Empty>Recommendations were not requested.</Empty>}
      </Panel>
      <IntegrationStatus />
    </div>
  );
}

function PreviewOverview({ projectId }: { projectId: string | null }) {
  return (
    <div className="flex flex-col gap-4" data-testid="live-defense-preview-overview">
      <p className="rounded-xl border border-line bg-panel p-5 text-sm text-ink">
        Sample layout only. Counts, map states and Q-values below are fixtures. They are not telemetry and not a loaded policy.
      </p>
      <DefenseMap
        nodes={PREVIEW_NODES}
        links={PREVIEW_LINKS}
        states={PREVIEW_STATES}
        title="Illustrative components (sample layout)"
        footnote="SAMPLE LAYOUT. States are drawn so the map chrome can be reviewed. They are not recorded health checks."
      />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Panel title="Example event feed" actions={<SourceTag mode="layout-preview" />}>
          <ol className="flex flex-col gap-2">
            {PREVIEW_EVENTS.map(event => (
              <li key={event.id} className="rounded-md border border-line bg-panel-2 p-2.5 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <Tag tone="warn">Sample</Tag>
                  <span className="font-medium">{event.title}</span>
                </div>
                <p className="mt-1 text-xs text-muted">{event.detail}</p>
              </li>
            ))}
          </ol>
        </Panel>
        <Panel title="Example incidents" actions={<Link className="text-xs text-accent hover:underline" href={liveDefenseHref(projectId, 'incidents', 'layout-preview')}>Investigate sample</Link>}>
          <ul className="flex flex-col gap-2">
            {PREVIEW_INCIDENTS.map(item => (
              <li key={item.id} className="rounded-md border border-line bg-panel-2 p-2.5 text-sm">
                <p className="font-medium">{item.title}</p>
                <p className="mt-1 text-xs text-muted">{item.summary}</p>
              </li>
            ))}
          </ul>
        </Panel>
      </div>
      <Panel title="Example recommendation chrome" actions={<Link className="text-xs text-accent hover:underline" href={liveDefenseHref(projectId, 'explain', 'layout-preview')}>Sample explainability</Link>}>
        <SimulationCaveat text={PREVIEW_RECOMMENDATIONS[0]?.caveat} />
        <p className="mt-2 text-sm">{actionInWords(PREVIEW_RECOMMENDATIONS[0]?.action ?? 'noop', PREVIEW_RECOMMENDATIONS[0]?.node ?? null)}</p>
      </Panel>
      <IntegrationStatus />
    </div>
  );
}

function IntegrationStatus() {
  return (
    <div data-testid="live-defense-api-coverage">
    <Panel title="API coverage for this dashboard">
      <p className="mb-3 text-sm text-muted">Live mode uses the endpoints that already exist. Missing ones stay empty — they are not filled with mock telemetry.</p>
      <h3 className="label-mono mb-2 text-xs">In use</h3>
      <ul className="mb-4 divide-y divide-line text-sm">
        {USED_LIVE_APIS.map(item => (
          <li key={item.path} className="flex flex-wrap justify-between gap-2 py-1.5">
            <Mono>{item.method} {item.path}</Mono>
            <span className="text-xs text-muted">{item.use}</span>
          </li>
        ))}
      </ul>
      <h3 className="label-mono mb-2 text-xs">Not in the control plane yet</h3>
      <ul className="divide-y divide-line text-sm">
        {MISSING_LIVE_APIS.map(item => (
          <li key={item.id} className="py-1.5">
            <p className="font-medium">{item.title}</p>
            <p className="text-xs text-muted">{item.reason}</p>
          </li>
        ))}
      </ul>
    </Panel>
    </div>
  );
}
