export interface MonitoringSummaryInput {
  monitoringEnabled: boolean;
  eventsKnown: boolean;
  eventCount: number;
  simulatedCount: number;
  eventsTruncated: boolean;
  recommendationsKnown: boolean;
  recommendationCount: number;
}

/** Separates recorded repository events from simulation recommendations. */
export function monitoringSummary(input: MonitoringSummaryInput): string {
  const watch = input.monitoringEnabled
    ? 'Monitoring is on for this project.'
    : 'Monitoring is off for this project.';
  if (!input.eventsKnown) {
    return `${watch} Recorded events have not loaded. Simulation recommendations are not repository events.`;
  }
  const count = input.eventsTruncated
    ? `The newest page has ${input.eventCount} recorded events`
    : input.eventCount === 0
      ? 'No recorded events yet'
      : `${input.eventCount} recorded event${input.eventCount === 1 ? '' : 's'}`;
  const simulated = input.simulatedCount > 0
    ? `, ${input.simulatedCount} labelled simulated`
    : '';
  const recommendations = !input.recommendationsKnown
    ? ' Simulation recommendations have not loaded.'
    : input.recommendationCount === 0
      ? ' No simulation recommendation is stored for this project.'
      : ` ${input.recommendationCount} simulation recommendation${input.recommendationCount === 1 ? ' is' : 's are'} listed separately and ${input.recommendationCount === 1 ? 'is' : 'are'} not applied to a real system.`;
  return `${watch} ${count}${simulated}.${recommendations} This page is not the Defense Lab.`;
}
