/* Generated from JSON Schema. Do not edit. */

export type ActiveDurationMs = number;
export type ActiveStartedAt = string | null;
/**
 * @minItems 1
 */
export type Attempts = [CoreRunAttempt, ...CoreRunAttempt[]];
export type CoreRunId = string;
export type Status = "created" | "running" | "completed" | "failed" | "cancelled";
export type CoreExperimentId = string;
export type ForestId = string;
export type AddedComponentIds = string[];
export type DesignId = string;
export type Origins = LayoutCaseOrigin[];
export type ComponentIds = string[];
export type Edges = [unknown, unknown][];
export type Cases = PersistedCaseV2[];
export type CreatedAt = string;
export type DesignId1 = string;
export type DesignTitle = string;
export type TheoreticalCombinations = number | string;
export type Designs = RunDesignSummaryV2[];
export type DisplayName = string;
export type Id = "single-row-facility-layout";
export type Version = "2.1.0";
export type DomainExperimentId = string;
export type DomainRunId = string;
export type FailureReason = "interrupted" | null;
export type FastArtifacts = {
  [k: string]: {
    [k: string]: number | string;
  };
} | null;
export type FastCounters = {
  [k: string]: number;
} | null;
export type CoreCases = number | string;
export type CyclePrunedBranches = number | string;
export type DegreePrunedBranches = number | string;
export type DuplicateForests = number | string;
export type ForbiddenCombinations = number | string;
export type InvalidCombinations = number | string;
export type StructuralInvalidCombinations = number | string;
export type TheoreticalCombinations1 = number | string;
export type ValidSelections = number | string;
export type GeneratorCursor = number | string;
export type Mode = "standard" | "high_performance";
export type SchemaVersion = "2.1.0";
export type Status1 = "created" | "running" | "completed" | "failed" | "cancelled";
export type UpdatedAt = string;

export interface DomainRunManifestV21 {
  active_duration_ms?: ActiveDurationMs;
  active_started_at?: ActiveStartedAt;
  cases: Cases;
  created_at: CreatedAt;
  designs?: Designs;
  display_name: DisplayName;
  domain: SingleRowDomainRefV21;
  domain_experiment_id: DomainExperimentId;
  domain_run_id: DomainRunId;
  failure_reason?: FailureReason;
  fast_artifacts?: FastArtifacts;
  fast_counters?: FastCounters;
  generation: GenerationMetricsV2;
  generator_cursor: GeneratorCursor;
  mode?: Mode;
  schema_version: SchemaVersion;
  status: Status1;
  updated_at: UpdatedAt;
}
export interface PersistedCaseV2 {
  attempts: Attempts;
  core_experiment_id: CoreExperimentId;
  forest_id: ForestId;
  origins: Origins;
  payload: LayoutCasePayload;
}
/**
 * A durable attempt to execute one projected case in CORE.
 */
export interface CoreRunAttempt {
  core_run_id: CoreRunId;
  status: Status;
}
export interface LayoutCaseOrigin {
  added_component_ids: AddedComponentIds;
  design_id: DesignId;
}
export interface LayoutCasePayload {
  component_ids: ComponentIds;
  edges: Edges;
}
export interface RunDesignSummaryV2 {
  design_id: DesignId1;
  design_title: DesignTitle;
  theoretical_combinations: TheoreticalCombinations;
}
export interface SingleRowDomainRefV21 {
  id: Id;
  version: Version;
}
export interface GenerationMetricsV2 {
  core_cases: CoreCases;
  cycle_pruned_branches: CyclePrunedBranches;
  degree_pruned_branches: DegreePrunedBranches;
  duplicate_forests: DuplicateForests;
  forbidden_combinations: ForbiddenCombinations;
  invalid_combinations: InvalidCombinations;
  structural_invalid_combinations: StructuralInvalidCombinations;
  theoretical_combinations: TheoreticalCombinations1;
  valid_selections: ValidSelections;
}
