'use client';

import { useSearchParams } from 'next/navigation';
import { ControlsDashboard } from '@/components/live-defense/controls';
import { useProject } from '@/components/project';
import { api } from '@/lib/api';
import { liveDefenseMode } from '@/lib/live-defense';
import { useResource } from '@/lib/use-resource';

export default function LiveDefenseControlsPage() {
  const { project } = useProject();
  const mode = liveDefenseMode(useSearchParams().get('preview'));
  const live = mode === 'live';
  const apps = useResource(live ? `ld-apps:${project.id}` : null, s => api().connectedApplications(project.id, { signal: s }));
  const controls = useResource(live ? `ld-controls:${project.id}` : null, s => api().liveControls(project.id, { signal: s }), 5000);
  const stops = useResource(live ? `ld-stop:${project.id}` : null, s => api().emergencyStop(project.id, { signal: s }), 5000);
  const reload = () => {
    apps.reload();
    controls.reload();
    stops.reload();
  };
  return (
    <ControlsDashboard
      mode={mode}
      projectId={project.id}
      apps={live ? apps : undefined}
      controls={live ? controls : undefined}
      stops={live ? stops : undefined}
      onChange={live ? reload : undefined}
    />
  );
}
