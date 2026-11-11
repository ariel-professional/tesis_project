/* Generated from JSON Schema. Do not edit. */

export type BaseCaseId = string;
export type ComparisonStatus = ("match" | "mismatch" | "not_applicable") | null;
export type CountingConvention = "undirected_paths_reverse_identified";
export type ExactValue = number | string | null;
export type Id = string;
export type Version = string;
export type ReferenceValue = number | string | null;
export type Value = number | string | null;
export type CandidateComponentIds = string[];
export type AddedComponentIds = string[];
export type Denominator = number | string;
export type Numerator = number | string;
export type CaseId = string;
export type ComponentIds = string[];
export type CoreRunId = string;
export type DesignId = string;
export type AffectedLocations = string[];
export type CoreCode = string;
export type Message = string;
export type Diagnostics = DomainDiagnostic[];
export type Dominated = boolean | null;
export type Edges = [unknown, unknown][];
export type Feasibility = "feasible" | "invalid_constraints" | "inconclusive";
export type ForestId = string;
export type IsolatedStationIds = string[];
export type Paths = string[][];
export type Code = string;
export type Message1 = string;
export type Limitations = DomainLimitation[];
export type MandatoryComponentIds = string[];
export type ParetoOptimal = boolean | null;
export type PrescribedEdgeCount = number;
export type CandidatesExamined = number | string;
export type DurationMs = number;
export type TotalUtility = number | string;
export type Utility = number | string;
export type Cases = LayoutCaseResult[];
export type DesignId1 = string;
export type DesignTitle = string;
export type InvalidCombinationCount = number | string;
export type InvalidCombinations = InvalidCombination[] | null;
export type AddedComponentIds1 = string[];
export type AffectedStationIds = string[];
export type CaseId1 = string;
export type ConflictingComponentIds = string[];
export type ConflictingEdges = [unknown, unknown][];
export type DesignId2 = string;
export type Reason = "cycle" | "degree_exceeded";
export type AffectedStationIds1 = string[];
export type CombinationCount = number | string;
export type ConflictingComponentIds1 = string[];
export type ConflictingEdges1 = [unknown, unknown][];
export type Reason1 = "cycle" | "degree_exceeded";
export type InvalidConflicts = InvalidConflictSummary[];
export type MandatoryComponentIds1 = string[];
export type ParetoCaseIds = string[];
export type TheoreticalCombinations = number | string;
export type ValidCaseCount = number | string;
export type Designs = LayoutDesignResult[];
export type Id1 = "single-row-facility-layout";
export type Version1 = "1.0.0";
export type DomainExperimentId = string;
export type DomainRunId = string;
export type Status = "completed" | "failed" | "cancelled";
export type CoreCases = number | string;
export type CyclePrunedBranches = number | string;
export type DegreePrunedBranches = number | string;
export type DuplicateForests = number | string;
export type InvalidCombinations1 = number | string;
export type TheoreticalCombinations1 = number | string;
export type ValidSelections = number | string;
export type Limitations1 = DomainLimitation[];
export type Definition = string;
export type Id2 = string;
export type Name = string;
export type SchemaVersion = "1.0.0";
export type Id3 = string;
export type Name1 = string;
export type Stations = Station[];
export type StudyDescription = string | null;
export type StudyId = string;
export type StudyTitle = string;

export interface SingleRowFacilityLayoutResult {
  designs: Designs;
  domain: SingleRowDomainRef;
  execution: DomainExecutionRef;
  generation: GenerationMetrics;
  limitations: Limitations1;
  primary_measure: MeasureDefinition;
  schema_version: SchemaVersion;
  stations: Stations;
  study_description: StudyDescription;
  study_id: StudyId;
  study_title: StudyTitle;
}
export interface LayoutDesignResult {
  base_case_id: BaseCaseId;
  base_layout_count: RouteCount | null;
  candidate_component_ids: CandidateComponentIds;
  cases: Cases;
  design_id: DesignId1;
  design_title: DesignTitle;
  invalid_combination_count: InvalidCombinationCount;
  invalid_combinations: InvalidCombinations;
  invalid_conflicts: InvalidConflicts;
  mandatory_component_ids: MandatoryComponentIds1;
  pareto_case_ids: ParetoCaseIds;
  theoretical_combinations: TheoreticalCombinations;
  valid_case_count: ValidCaseCount;
}
export interface RouteCount {
  comparison_status: ComparisonStatus;
  counting_convention: CountingConvention;
  exact_value: ExactValue;
  method: ProducerRef | null;
  reference_value: ReferenceValue;
  value: Value;
}
export interface ProducerRef {
  id: Id;
  version: Version;
}
export interface LayoutCaseResult {
  added_component_ids: AddedComponentIds;
  availability_ratio: ExactFraction | null;
  case_id: CaseId;
  compatible_layout_count: RouteCount | null;
  component_ids: ComponentIds;
  core_run_id: CoreRunId;
  design_id: DesignId;
  diagnostics: Diagnostics;
  dominated: Dominated;
  edges: Edges;
  feasibility: Feasibility;
  forest_id: ForestId;
  forest_structure: LinearForestStructure;
  limitations: Limitations;
  mandatory_component_ids: MandatoryComponentIds;
  pareto_optimal: ParetoOptimal;
  prescribed_edge_count: PrescribedEdgeCount;
  restrictiveness_ratio: ExactFraction | null;
  technical_metrics: TechnicalMetrics | null;
  total_utility: TotalUtility;
  utility: Utility;
}
export interface ExactFraction {
  denominator: Denominator;
  numerator: Numerator;
}
export interface DomainDiagnostic {
  affected_locations: AffectedLocations;
  core_code: CoreCode;
  message: Message;
}
export interface LinearForestStructure {
  isolated_station_ids: IsolatedStationIds;
  paths: Paths;
}
export interface DomainLimitation {
  code: Code;
  message: Message1;
}
export interface TechnicalMetrics {
  candidates_examined: CandidatesExamined;
  duration_ms: DurationMs;
}
export interface InvalidCombination {
  added_component_ids: AddedComponentIds1;
  affected_station_ids: AffectedStationIds;
  case_id: CaseId1;
  conflicting_component_ids: ConflictingComponentIds;
  conflicting_edges: ConflictingEdges;
  design_id: DesignId2;
  reason: Reason;
}
export interface InvalidConflictSummary {
  affected_station_ids: AffectedStationIds1;
  combination_count: CombinationCount;
  conflicting_component_ids: ConflictingComponentIds1;
  conflicting_edges: ConflictingEdges1;
  reason: Reason1;
}
export interface SingleRowDomainRef {
  id: Id1;
  version: Version1;
}
export interface DomainExecutionRef {
  domain_experiment_id: DomainExperimentId;
  domain_run_id: DomainRunId;
  status: Status;
}
export interface GenerationMetrics {
  core_cases: CoreCases;
  cycle_pruned_branches: CyclePrunedBranches;
  degree_pruned_branches: DegreePrunedBranches;
  duplicate_forests: DuplicateForests;
  invalid_combinations: InvalidCombinations1;
  theoretical_combinations: TheoreticalCombinations1;
  valid_selections: ValidSelections;
}
export interface MeasureDefinition {
  definition: Definition;
  id: Id2;
  name: Name;
}
export interface Station {
  id: Id3;
  name: Name1;
}
