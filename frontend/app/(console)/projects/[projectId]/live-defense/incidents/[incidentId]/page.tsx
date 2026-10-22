'use client';

import { useSearchParams } from 'next/navigation';
import { InvestigationDetail } from '@/components/live-defense/investigation';
import { useParam, useProject } from '@/components/project';
import { api } from '@/lib/api';
import { liveDefenseMode } from '@/lib/live-defense';
import { useResource } from '@/lib/use-resource';

export default function LiveDefenseIncidentDetailPage() {
  const { project } = useProject();
  const incidentId = decodeURIComponent(useParam('incidentId'));
  const mode = liveDefenseMode(useSearchParams().get('preview'));
  const live = mode === 'live';
  const detail = useResource(live ? `ld-incident:${incidentId}` : null, s => api().incident(incidentId, { signal: s }), 15000);
  return <InvestigationDetail mode={mode} projectId={project.id} incidentId={incidentId} detail={live ? detail : undefined} />;
}
