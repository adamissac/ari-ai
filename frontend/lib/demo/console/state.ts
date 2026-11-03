import { DEMO_REPOS } from '@/lib/demo/data';

/** sessionStorage key of the demo account's simulated changes (lib/demo/console/sim.ts). */
export const DEMO_SIM_STORAGE_KEY = 'ari-demo-sim-v1';

/** Fictional Lumen Pay repositories the demo GitHub App installation can reach. */
export const DEMO_GITHUB_REPOS = DEMO_REPOS.filter(repo => repo.org === 'lumen-pay');

/** Forget every simulated change (sign-in and exit). */
export function resetDemoSimulation(): void {
  try { globalThis.sessionStorage?.removeItem(DEMO_SIM_STORAGE_KEY); } catch { /* nothing stored */ }
}
