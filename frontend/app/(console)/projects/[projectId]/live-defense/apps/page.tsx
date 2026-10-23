'use client';

import { useSearchParams } from 'next/navigation';
import { StagingApps } from '@/components/live-defense/apps';
import { useProject } from '@/components/project';
import { api } from '@/lib/api';
import { liveDefenseMode } from '@/lib/live-defense';
import { useResource } from '@/lib/use-resource';

export default function LiveDefenseAppsPage() {
  const { project } = useProject();
  const mode = liveDefenseMode(useSearchParams().get('preview'));
  const live = mode === 'live';
  const apps = useResource(live ? `ld-apps:${project.id}` : null, s => api().connectedApplications(project.id, { signal: s }));
  const tokens = useResource(live ? `ld-tokens:${project.id}` : null, s => api().ingestTokens(project.id, { signal: s }));
  const health = useResource(live ? `ld-health:${project.id}` : null, s => api().defenseHealth(project.id, { signal: s }), 15000);
  const grants = useResource(live ? `ld-grants:${project.id}` : null, s => api().controlGrants(project.id, { signal: s }));
  const reload = () => {
    apps.reload();
    tokens.reload();
    health.reload();
    grants.reload();
  };
  return (
    <StagingApps
      mode={mode}
      projectId={project.id}
      apps={live ? apps : undefined}
      tokens={live ? tokens : undefined}
      health={live ? health : undefined}
      grants={live ? grants : undefined}
      onChange={live ? reload : undefined}
    />
  );
}
