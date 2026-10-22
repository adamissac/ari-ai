'use client';

import { useSearchParams } from 'next/navigation';
import { Explainability } from '@/components/live-defense/explain';
import { useProject } from '@/components/project';
import { api } from '@/lib/api';
import { liveDefenseMode } from '@/lib/live-defense';
import { useResource } from '@/lib/use-resource';

export default function LiveDefenseExplainPage() {
  const { project } = useProject();
  const mode = liveDefenseMode(useSearchParams().get('preview'));
  const live = mode === 'live';
  const recs = useResource(live ? `ld-recs:${project.id}` : null, s => api().defenseRecommendations(project.id, { signal: s }));
  const evals = useResource(live ? `ld-rle:${project.id}` : null, s => api().rlEvaluations(project.id, { signal: s }));
  return <Explainability mode={mode} recs={live ? recs : undefined} evals={live ? evals : undefined} />;
}
