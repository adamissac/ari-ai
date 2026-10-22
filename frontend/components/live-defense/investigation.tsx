'use client';

import type { Incident, IncidentDetail } from '@hackatl/frontend-transport';
import Link from 'next/link';
import { SourceTag } from '@/components/live-defense/common';
import { Async, Empty, Mono, Panel, Tag, Time } from '@/components/ui';
import { liveDefenseHref, type LiveDefenseMode } from '@/lib/live-defense';
import { PREVIEW_INCIDENTS, previewIncident } from '@/lib/live-defense-preview';
import { LIFECYCLE, STATE_LABEL } from '@/lib/incidents';
import type { Resource } from '@/lib/use-resource';

export function InvestigationList({
  mode,
  projectId,
  incidents,
}: {
  mode: LiveDefenseMode;
  projectId: string | null;
  incidents?: Resource<{ items: Incident[] }>;
}) {
  if (mode === 'layout-preview') {
    return (
      <Panel title="Sample investigations" actions={<SourceTag mode="layout-preview" />}>
        <ul className="flex flex-col gap-2">
          {PREVIEW_INCIDENTS.map(item => (
            <li key={item.id}>
              <Link href={`${liveDefenseHref(projectId, 'incidents', 'layout-preview')}/${encodeURIComponent(item.id)}`} className="block rounded-md border border-line bg-panel-2 p-3 hover:bg-white">
                <p className="font-medium">{item.title}</p>
                <p className="mt-1 text-xs text-muted">{item.summary}</p>
              </Link>
            </li>
          ))}
        </ul>
      </Panel>
    );
  }
  return (
    <Panel title="Incidents available to investigate" actions={<SourceTag mode="live" />}>
      <p className="mb-3 text-sm text-muted">
        These are NIST SP 800-61 records from the control plane. Human actions (triage, two-person gates, closure) stay on the{' '}
        {projectId ? <Link className="text-accent hover:underline" href={`/projects/${projectId}/incidents`}>Incidents</Link> : 'Incidents'} page.
        This view does not run adapters.
      </p>
      {incidents ? (
        <Async resource={incidents} label="incidents">
          {page => page.items.length === 0 ? <Empty>No incidents. Open one from Monitoring or the Incidents page.</Empty> : (
            <ul className="flex flex-col gap-2">
              {page.items.map(item => (
                <li key={item.id}>
                  <Link href={`${liveDefenseHref(projectId, 'incidents')}/${item.id}`} className="block rounded-md border border-line bg-panel-2 p-3 text-left hover:bg-white" data-testid={`live-defense-incident-${item.id}`}>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-medium">{item.title}</span>
                      <span className="flex gap-1">{item.simulated && <Tag tone="warn">Synthetic</Tag>}<Tag>{STATE_LABEL[item.state]}</Tag></span>
                    </div>
                    <p className="mt-1 text-xs text-muted">CSF {item.csf_function} · {item.severity ?? 'unscored'} · opened <Time iso={item.opened_at} /></p>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Async>
      ) : <Empty>Incidents were not requested.</Empty>}
    </Panel>
  );
}

export function InvestigationDetail({
  mode,
  projectId,
  incidentId,
  detail,
}: {
  mode: LiveDefenseMode;
  projectId: string | null;
  incidentId: string;
  detail?: Resource<IncidentDetail>;
}) {
  if (mode === 'layout-preview') {
    const sample = previewIncident(incidentId);
    if (!sample) return <Empty>That sample incident is not in the layout-preview fixtures.</Empty>;
    return (
      <div className="flex flex-col gap-4" data-testid="live-defense-preview-investigation">
        <Panel title={sample.title} actions={<SourceTag mode="layout-preview" />}>
          <p className="text-sm text-muted">{sample.summary}</p>
          <p className="mt-2 text-xs text-muted">Linked in this sample: {sample.linked.events} events · {sample.linked.findings} findings · {sample.linked.recommendations} recommendations</p>
        </Panel>
        <Panel title="Sample timeline">
          <ol className="flex flex-col gap-2">
            {sample.timeline.map((entry, index) => (
              <li key={`${entry.label}-${index}`} className="rounded-md border border-line bg-panel-2 p-2.5 text-sm">
                <p className="font-medium">{entry.label}</p>
                <p className="text-xs text-muted">{entry.note}</p>
              </li>
            ))}
          </ol>
        </Panel>
        <Link className="text-sm text-accent hover:underline" href={liveDefenseHref(projectId, 'incidents', 'layout-preview')}>Back to sample list</Link>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-4">
      {detail ? (
        <Async resource={detail} label="incident">
          {({ incident }) => (
            <>
              <Panel title={incident.title} actions={<>{incident.simulated && <Tag tone="warn">Synthetic drill</Tag>}<SourceTag mode="live" /></>}>
                <Lifecycle state={incident.state} />
                <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs text-muted">
                  <dt>CSF function</dt><dd>{incident.csf_function}</dd>
                  <dt>Owner</dt><dd>{incident.owner ? <Mono>{incident.owner}</Mono> : 'unassigned'}</dd>
                  <dt>Severity</dt><dd>{incident.severity ?? 'unscored'} · priority {incident.business_priority}</dd>
                  {incident.triage && <><dt>Triage</dt><dd>{incident.triage.decision.replaceAll('_', ' ')} · {incident.triage.category} — {incident.triage.rationale}</dd></>}
                  <dt>Linked</dt>
                  <dd>
                    {incident.finding_ids.length} findings · {incident.monitoring_event_ids.length} events · {incident.verification_ids.length} verifications · {incident.recommendation_ids.length} recommendations
                  </dd>
                </dl>
                <p className="mt-3 text-sm text-muted">
                  To triage, assign, or close this incident, use the{' '}
                  {projectId ? <Link className="text-accent hover:underline" href={`/projects/${projectId}/incidents`}>Incidents workspace</Link> : 'Incidents workspace'}.
                  Live Defense does not add apply / isolate / rate-limit actions.
                </p>
              </Panel>
              <Panel title="Recorded timeline">
                {incident.timeline.length === 0 ? <Empty>No timeline entries.</Empty> : (
                  <ol className="flex flex-col gap-2">
                    {incident.timeline.map((entry, index) => (
                      <li key={`${entry.at}-${index}`} className="rounded-md border border-line bg-panel-2 p-2.5 text-sm">
                        <div className="flex flex-wrap items-center gap-2">
                          <Tag>{entry.action.replaceAll('_', ' ')}</Tag>
                          {entry.to_state && <Tag tone="info">{STATE_LABEL[entry.to_state]}</Tag>}
                          <span className="text-xs text-muted"><Time iso={entry.at} /> · {entry.actor}</span>
                        </div>
                        {entry.note && <p className="mt-1 text-muted">{entry.note}</p>}
                        {entry.csf_refs.length > 0 && <p className="mt-1 text-xs text-faint">CSF {entry.csf_refs.join(', ')}</p>}
                      </li>
                    ))}
                  </ol>
                )}
              </Panel>
            </>
          )}
        </Async>
      ) : <Empty>Incident detail was not requested.</Empty>}
      <Link className="text-sm text-accent hover:underline" href={liveDefenseHref(projectId, 'incidents')}>Back to investigation list</Link>
    </div>
  );
}

function Lifecycle({ state }: { state: Incident['state'] }) {
  return (
    <ol className="flex flex-wrap gap-1" aria-label="NIST incident lifecycle">
      {LIFECYCLE.map(step => {
        const current = step === state;
        const past = LIFECYCLE.indexOf(step) < LIFECYCLE.indexOf(state);
        return (
          <li key={step} className={`rounded-full border px-2 py-0.5 text-[11px] ${current ? 'border-brand bg-brand/10 text-ink' : past ? 'border-line text-muted' : 'border-dashed border-line text-faint'}`}>
            {STATE_LABEL[step]}
          </li>
        );
      })}
    </ol>
  );
}
