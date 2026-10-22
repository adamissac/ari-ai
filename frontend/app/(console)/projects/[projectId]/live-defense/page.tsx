'use client';

import { useSearchParams } from 'next/navigation';
import { LiveOverview } from '@/components/live-defense/overview';
import { useProject } from '@/components/project';
import { api } from '@/lib/api';
import { liveDefenseMode } from '@/lib/live-defense';
import { useResource } from '@/lib/use-resource';

export default function LiveDefenseOverviewPage() {
  const { project, reloadProject } = useProject();
  const mode = liveDefenseMode(useSearchParams().get('preview'));
  const live = mode === 'live';
  const events = useResource(live ? `ld-events:${project.id}` : null, s => api().monitoringEvents(project.id, { signal: s }), 10000);
  const incidents = useResource(live ? `ld-incidents:${project.id}` : null, s => api().incidents(project.id, { signal: s }), 15000);
  const recs = useResource(live ? `ld-recs:${project.id}` : null, s => api().defenseRecommendations(project.id, { signal: s }));
  const reassess = useResource(live ? `ld-reassess:${project.id}` : null, s => api().reassessments(project.id, { signal: s }), 10000);
  const health = useResource(live ? `ld-health:${project.id}` : null, s => api().defenseHealth(project.id, { signal: s }), 15000);
  const graph = useResource(live ? `ld-graph:${project.id}` : null, s => api().defenseGraph(project.id, { signal: s }), 15000);
  const apps = useResource(live ? `ld-apps:${project.id}` : null, s => api().connectedApplications(project.id, { signal: s }));
  return (
    <LiveOverview
      mode={mode}
      projectId={project.id}
      project={project}
      reloadProject={reloadProject}
      events={live ? events : undefined}
      incidents={live ? incidents : undefined}
      recs={live ? recs : undefined}
      reassess={live ? reassess : undefined}
      health={live ? health : undefined}
      graph={live ? graph : undefined}
      apps={live ? apps : undefined}
    />
  );
}
