'use client';

import { useSearchParams } from 'next/navigation';
import { InvestigationList } from '@/components/live-defense/investigation';
import { useProject } from '@/components/project';
import { api } from '@/lib/api';
import { liveDefenseMode } from '@/lib/live-defense';
import { useResource } from '@/lib/use-resource';

export default function LiveDefenseIncidentsPage() {
  const { project } = useProject();
  const mode = liveDefenseMode(useSearchParams().get('preview'));
  const live = mode === 'live';
  const incidents = useResource(live ? `ld-incidents:${project.id}` : null, s => api().incidents(project.id, { signal: s }), 15000);
  return <InvestigationList mode={mode} projectId={project.id} incidents={live ? incidents : undefined} />;
}
