'use client';

import { InvestigationDetail } from '@/components/live-defense/investigation';
import { useParam } from '@/components/project';

export default function PilotIncidentPage() {
  const incidentId = decodeURIComponent(useParam('incidentId'));
  return <InvestigationDetail mode="layout-preview" projectId={null} incidentId={incidentId} />;
}
