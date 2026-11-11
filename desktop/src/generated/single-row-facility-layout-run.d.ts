/* Generated from JSON Schema. Do not edit. */

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
export type Cases = PersistedCase[];
export type CreatedAt = string;
export type DisplayName = string;
export type Id = "single-row-facility-layout";
export type Version = "1.0.0";
export type DomainExperimentId = string;
export type DomainRunId = string;
export type CoreCases = number | string;
export type CyclePrunedBranches = number | string;
export type DegreePrunedBranches = number | string;
export type DuplicateForests = number | string;
export type InvalidCombinations = number | string;
export type TheoreticalCombinations = number | string;
export type ValidSelections = number | string;
export type GeneratorCursor = number | string;
export type SchemaVersion = "1.0.0";
export type Status1 = "created" | "running" | "completed" | "failed" | "cancelled";
export type UpdatedAt = string;

export interface DomainRunManifest {
  cases: Cases;
  created_at: CreatedAt;
  display_name: DisplayName;
  domain: SingleRowDomainRef;
  domain_experiment_id: DomainExperimentId;
  domain_run_id: DomainRunId;
  generation: GenerationMetrics;
  generator_cursor: GeneratorCursor;
  schema_version: SchemaVersion;
  status: Status1;
  updated_at: UpdatedAt;
}
export interface PersistedCase {
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
export interface SingleRowDomainRef {
  id: Id;
  version: Version;
}
export interface GenerationMetrics {
  core_cases: CoreCases;
  cycle_pruned_branches: CyclePrunedBranches;
  degree_pruned_branches: DegreePrunedBranches;
  duplicate_forests: DuplicateForests;
  invalid_combinations: InvalidCombinations;
  theoretical_combinations: TheoreticalCombinations;
  valid_selections: ValidSelections;
}
