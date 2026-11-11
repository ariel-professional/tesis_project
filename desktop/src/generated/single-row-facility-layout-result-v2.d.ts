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
export type FirstStationId = string;
export type ForwardValue = number | string;
export type ReverseValue = number | string | null;
export type SecondStationId = string;
export type Total = number | string;
export type Contributions = AdjacencyValueContribution[];
export type Diagnostics = string[];
export type Directed = boolean;
export type Direction = "maximize" | "minimize";
export type Limitations = string[];
export type MatrixId = string;
export type ObjectiveId = string;
export type ObjectiveVersion = "1";
export type ReferencePeriod = string | null;
export type Status = "conclusive" | "inconclusive" | "not_applicable" | "not_calculated" | "invalid";
export type Total1 = number | string | null;
export type Unit = string;
export type AdjacencyValues = AdjacencyValueResult[];
export type FirstStationId1 = string;
export type ForwardQuantity = number | string;
export type ReverseQuantity = number | string | null;
export type SecondStationId1 = string;
export type Total2 = number | string;
export type Contributions1 = FlowContribution[];
export type Diagnostics1 = string[];
export type Directed1 = boolean;
export type Direction1 = "maximize" | "minimize";
export type Horizon = string;
export type Limitations1 = string[];
export type ObjectiveId1 = "captured-adjacency-flow";
export type ObjectiveVersion1 = "1";
export type Status1 = "conclusive" | "inconclusive" | "not_applicable" | "not_calculated" | "invalid";
export type Total3 = number | string | null;
export type Unit1 = string;
export type CaseId = string;
export type ComponentIds = string[];
export type CoreRunId = string;
export type DesignId = string;
export type AffectedLocations = string[];
export type CoreCode = string;
export type Message = string;
export type Diagnostics2 = DomainDiagnostic[];
export type Edges = [unknown, unknown][];
export type Feasibility = "feasible" | "invalid_constraints" | "inconclusive";
export type Cause = "safety" | "cross_contamination" | "noise" | "temperature" | "privacy" | "interference" | "process";
export type Explanation = string;
export type FirstStationId2 = string;
export type Policy = "warn";
export type Provenance = string;
export type SecondStationId2 = string;
export type Findings = AdjacencyFinding[];
export type ForestId = string;
export type IsolatedStationIds = string[];
export type Paths = string[][];
export type Code = string;
export type Message1 = string;
export type Limitations2 = DomainLimitation[];
export type MandatoryComponentIds = string[];
export type ObjectiveId2 = string;
export type OtherCaseId = string;
export type OtherValue = ExactFraction | string;
export type Denominator = number | string;
export type Numerator = number | string;
export type PreferredCaseId = string;
export type PreferredValue = ExactFraction | string;
export type Differences = ParetoDifference[];
export type Dominated = boolean | null;
export type DominatedByCaseIds = string[];
export type ObjectiveRefs = string[];
export type ParetoOptimal = boolean | null;
export type Status2 = "conclusive" | "inconclusive";
export type PrescribedEdgeCount = number;
export type Denominator1 = number;
export type Diagnostics3 = string[];
export type Direction2 = "maximize" | "minimize";
export type GuaranteedPairs = [unknown, unknown][];
export type Level = "A" | "E" | "I" | "O";
export type Limitations3 = string[];
export type Numerator1 = number;
export type ObjectiveId3 = string;
export type ObjectiveVersion2 = "1";
export type PendingPairs = [unknown, unknown][];
export type Status3 = "conclusive" | "inconclusive" | "not_applicable" | "not_calculated" | "invalid";
export type Unit2 = string;
export type RelCloseness = RelLevelResult[];
export type BaseLayoutCount = number | null;
export type CompatibleLayoutCount = number | null;
export type Diagnostics4 = string[];
export type Direction3 = "maximize" | "minimize";
export type Limitations4 = string[];
export type ObjectiveId4 = string;
export type ObjectiveVersion3 = "1";
export type Status4 = "conclusive" | "inconclusive" | "not_applicable" | "not_calculated" | "invalid";
export type Unit3 = string;
export type CandidatesExamined = number | string;
export type DurationMs = number;
export type Cases = LayoutCaseResultV2[];
export type DesignId1 = string;
export type DesignTitle = string;
export type InvalidCombinationCount = number | string;
export type AffectedStationIds = string[];
export type Cause1 = string | null;
export type CombinationCount = number | string;
export type ConflictingComponentIds = string[];
export type ConflictingEdges = [unknown, unknown][];
export type Explanation1 = string | null;
export type Provenance1 = string | null;
export type Reason = "cycle" | "degree_exceeded" | "forbidden";
export type InvalidCombinationSummaries = InvalidCombinationSummaryV2[];
export type MandatoryComponentIds1 = string[];
export type ParetoCaseIds = string[];
export type TheoreticalCombinations = number | string;
export type ValidCaseCount = number | string;
export type Designs = LayoutDesignResultV2[];
export type Id1 = "single-row-facility-layout";
export type Version1 = "2.0.0";
export type CoreCases = number | string;
export type CyclePrunedBranches = number | string;
export type DegreePrunedBranches = number | string;
export type DuplicateForests = number | string;
export type ForbiddenCombinations = number | string;
export type InvalidCombinations = number | string;
export type StructuralInvalidCombinations = number | string;
export type TheoreticalCombinations1 = number | string;
export type ValidSelections = number | string;
export type Limitations5 = DomainLimitation[];
export type Classification = "criterion" | "indicator";
export type DecisionQuestion = string;
export type Direction4 = "maximize" | "minimize";
export type DirectionMode = "fixed" | "per_instance";
/**
 * @minItems 1
 */
export type Evidence = [string, ...string[]];
export type Formula = string;
export type Id2 = string;
/**
 * @minItems 1
 */
export type Limitations6 = [string, ...string[]];
export type Name = string;
export type RepeatableInput = boolean;
/**
 * @minItems 1
 */
export type RequiredInputs = [string, ...string[]];
export type Scope = "case" | "prescribed_adjacencies";
export type Summary = string;
export type Unit4 = string;
export type Version2 = "1";
export type ObjectiveSnapshots = ObjectiveSnapshot[];
export type SchemaVersion = "2.0.0";
export type Id3 = string;
export type Name1 = string;
export type Stations = StationV2[];
export type StudyDescription = string | null;
export type StudyId = string;
export type StudyTitle = string;

export interface SingleRowFacilityLayoutResultV2 {
  designs: Designs;
  domain: SingleRowDomainRefV2;
  execution: Execution;
  generation: GenerationMetricsV2;
  limitations: Limitations5;
  objective_snapshots: ObjectiveSnapshots;
  schema_version: SchemaVersion;
  stations: Stations;
  study_description: StudyDescription;
  study_id: StudyId;
  study_title: StudyTitle;
}
export interface LayoutDesignResultV2 {
  base_case_id: BaseCaseId;
  base_layout_count: RouteCount | null;
  candidate_component_ids: CandidateComponentIds;
  cases: Cases;
  design_id: DesignId1;
  design_title: DesignTitle;
  invalid_combination_count: InvalidCombinationCount;
  invalid_combination_summaries: InvalidCombinationSummaries;
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
export interface LayoutCaseResultV2 {
  added_component_ids: AddedComponentIds;
  adjacency_values?: AdjacencyValues;
  captured_flow?: CapturedFlowResult | null;
  case_id: CaseId;
  compatible_layout_count: RouteCount | null;
  component_ids: ComponentIds;
  core_run_id: CoreRunId;
  design_id: DesignId;
  diagnostics: Diagnostics2;
  edges: Edges;
  feasibility: Feasibility;
  findings?: Findings;
  forest_id: ForestId;
  forest_structure: LinearForestStructure;
  limitations: Limitations2;
  mandatory_component_ids: MandatoryComponentIds;
  pareto_classification: ParetoClassification;
  prescribed_edge_count: PrescribedEdgeCount;
  rel_closeness?: RelCloseness;
  retained_layouts?: RetainedLayoutsResult | null;
  technical_metrics: TechnicalMetrics | null;
}
export interface AdjacencyValueResult {
  contributions?: Contributions;
  diagnostics?: Diagnostics;
  directed: Directed;
  direction: Direction;
  limitations?: Limitations;
  matrix_id: MatrixId;
  objective_id: ObjectiveId;
  objective_version: ObjectiveVersion;
  reference_period?: ReferencePeriod;
  status: Status;
  total?: Total1;
  unit: Unit;
}
export interface AdjacencyValueContribution {
  first_station_id: FirstStationId;
  forward_value: ForwardValue;
  reverse_value?: ReverseValue;
  second_station_id: SecondStationId;
  total: Total;
}
export interface CapturedFlowResult {
  contributions?: Contributions1;
  diagnostics?: Diagnostics1;
  directed: Directed1;
  direction: Direction1;
  horizon: Horizon;
  limitations?: Limitations1;
  objective_id: ObjectiveId1;
  objective_version: ObjectiveVersion1;
  status: Status1;
  total?: Total3;
  unit: Unit1;
}
export interface FlowContribution {
  first_station_id: FirstStationId1;
  forward_quantity: ForwardQuantity;
  reverse_quantity?: ReverseQuantity;
  second_station_id: SecondStationId1;
  total: Total2;
}
export interface DomainDiagnostic {
  affected_locations: AffectedLocations;
  core_code: CoreCode;
  message: Message;
}
export interface AdjacencyFinding {
  cause: Cause;
  explanation: Explanation;
  first_station_id: FirstStationId2;
  policy: Policy;
  provenance: Provenance;
  second_station_id: SecondStationId2;
}
export interface LinearForestStructure {
  isolated_station_ids: IsolatedStationIds;
  paths: Paths;
}
export interface DomainLimitation {
  code: Code;
  message: Message1;
}
export interface ParetoClassification {
  differences?: Differences;
  dominated: Dominated;
  dominated_by_case_ids?: DominatedByCaseIds;
  objective_refs: ObjectiveRefs;
  pareto_optimal: ParetoOptimal;
  status: Status2;
}
export interface ParetoDifference {
  objective_id: ObjectiveId2;
  other_case_id: OtherCaseId;
  other_value: OtherValue;
  preferred_case_id: PreferredCaseId;
  preferred_value: PreferredValue;
}
export interface ExactFraction {
  denominator: Denominator;
  numerator: Numerator;
}
export interface RelLevelResult {
  denominator: Denominator1;
  diagnostics?: Diagnostics3;
  direction: Direction2;
  fraction: ExactFraction;
  guaranteed_pairs: GuaranteedPairs;
  level: Level;
  limitations?: Limitations3;
  numerator: Numerator1;
  objective_id: ObjectiveId3;
  objective_version: ObjectiveVersion2;
  pending_pairs: PendingPairs;
  status: Status3;
  unit: Unit2;
}
export interface RetainedLayoutsResult {
  base_layout_count?: BaseLayoutCount;
  compatible_layout_count?: CompatibleLayoutCount;
  diagnostics?: Diagnostics4;
  direction: Direction3;
  fraction?: ExactFraction | null;
  limitations?: Limitations4;
  objective_id: ObjectiveId4;
  objective_version: ObjectiveVersion3;
  status: Status4;
  unit: Unit3;
}
export interface TechnicalMetrics {
  candidates_examined: CandidatesExamined;
  duration_ms: DurationMs;
}
export interface InvalidCombinationSummaryV2 {
  affected_station_ids: AffectedStationIds;
  cause?: Cause1;
  combination_count: CombinationCount;
  conflicting_component_ids: ConflictingComponentIds;
  conflicting_edges: ConflictingEdges;
  explanation?: Explanation1;
  provenance?: Provenance1;
  reason: Reason;
}
export interface SingleRowDomainRefV2 {
  id: Id1;
  version: Version1;
}
export interface Execution {
  [k: string]: unknown;
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
export interface ObjectiveSnapshot {
  definition: ObjectiveDefinition;
}
export interface ObjectiveDefinition {
  classification: Classification;
  decision_question: DecisionQuestion;
  direction: Direction4;
  direction_mode?: DirectionMode;
  evidence: Evidence;
  formula: Formula;
  id: Id2;
  limitations: Limitations6;
  name: Name;
  repeatable_input?: RepeatableInput;
  required_inputs: RequiredInputs;
  scope: Scope;
  summary: Summary;
  unit: Unit4;
  version: Version2;
}
export interface StationV2 {
  id: Id3;
  name: Name1;
}
