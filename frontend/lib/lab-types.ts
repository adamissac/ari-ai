/**
 * Shape of rl-defense/fixtures/defense_lab.schema.json (owned by Adam). The
 * server validates every bundle against that schema before it reaches the
 * browser, so these types never describe unvalidated data.
 */
export interface MetricCI { mean: number | null; ci95: [number | null, number | null] }
export interface LabNode { name: string; criticality: number; exposed: boolean; finding_severity: number }
export interface LabScenario { name: string; config_hash: string; split: 'eval'; horizon: number; nodes: LabNode[]; edges: [string, string][] }
export interface LabPolicyMetrics { policy: string; pooled: Record<string, MetricCI>; per_scenario: Record<string, Record<string, MetricCI>> }
export type HiddenStage = 'none' | 'foothold' | 'escalated' | 'impact';
export interface LabNodeState {
  node: string; alert_rate: number; anomaly_score: number; monitoring_level: number;
  rate_limited: boolean; isolated: boolean; reassessment_pending: boolean; hidden_stage_ground_truth: HiddenStage;
}
export interface LabStep { t: number; action: string; reward: number; reward_components: Record<string, number>; nodes: LabNodeState[] }
export interface LabEpisode {
  policy: string; scenario: string; episode_seed: number; training_seed: number | null;
  total_return: number; compromised: boolean; impact_nodes: string[]; steps: LabStep[];
}
export interface DefenseLabBundle {
  schema_version: string; env_id: string; simulation_only: true; caveat: string; source_run: string; git_sha: string;
  checkpoint_sha256: Record<string, string>; training_seeds: number[]; episodes_per_config_per_seed: number;
  scenarios: LabScenario[]; metrics: LabPolicyMetrics[]; episodes: LabEpisode[];
}
export interface BundleProvenance { protocol: string; path: string; sha256: string; bytes: number; schemaPath: string }
export interface BundleResponse { provenance: BundleProvenance; bundle: DefenseLabBundle }
