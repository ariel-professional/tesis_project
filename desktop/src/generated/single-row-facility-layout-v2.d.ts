/* Generated from JSON Schema. Do not edit. */

export type AdjacencyFlow = FlowMatrix | AdjacencyValueMatrix[] | null;
export type Directed = boolean;
/**
 * @minItems 1
 */
export type Entries = [FlowEntry, ...FlowEntry[]];
export type FromStationId = string;
export type Quantity = number | string;
export type ToStationId = string;
export type Horizon = string;
export type Provenance = string;
export type Unit = string;
export type Description = string;
export type Directed1 = boolean;
export type Direction = "maximize" | "minimize";
/**
 * @minItems 1
 */
export type Entries1 = [AdjacencyValueEntry, ...AdjacencyValueEntry[]];
export type FromStationId1 = string;
export type ToStationId1 = string;
export type Value = number | string;
export type Id = string;
export type Name = string;
export type Provenance1 = string;
export type ReferencePeriod = string | null;
export type Unit1 = string;
/**
 * @minItems 1
 */
export type Requirements = [RelRequirement, ...RelRequirement[]];
export type FirstStationId = string;
export type Level = "A" | "E" | "I" | "O" | "U" | "X";
export type Provenance2 = string;
export type Reason = string;
export type SecondStationId = string;
export type RetainedCompatibleLayouts = boolean;
export type Id1 = string;
export type Version = "1";
export type SelectedObjectives = ObjectiveReference[];
export type Cause = "safety" | "cross_contamination" | "noise" | "temperature" | "privacy" | "interference" | "process";
export type Explanation = string;
export type FirstStationId1 = string;
export type Policy = "forbidden" | "warn";
export type Provenance3 = string;
export type SecondStationId1 = string;
export type UndesiredPrescribedAdjacencies = UndesiredAdjacency[];
export type Id2 = "single-row-facility-layout";
export type Version1 = "2.0.0";
export type CountingConvention = "undirected_paths_reverse_identified";
export type CancellationGraceMs = number;
export type ControlConnectTimeoutMs = number;
export type ControlMaxMessageBytes = number;
export type ControlResponseTimeoutMs = number;
export type EventMaxPayloadBytes = number;
export type ExactTimeoutMs = number;
export type InputMaxBytes = number;
export type MaxN = number;
export type ReferenceMaxN = number;
export type ReferenceTimeoutMs = number;
export type RunnerLogBackupCount = number;
export type RunnerLogMaxBytes = number;
export type WorkerMaxMessageBytes = number;
export type Engine = "auto";
export type Engine1 = "bruteforce_python_v1";
export type PersistEvents = boolean;
export type Policy1 = "normal" | "debug";
export type InvalidCombinations = "summary" | "full";
export type SchemaVersion = "2.0.0";
export type Kind = "file";
export type MediaType = "image/png" | "image/jpeg" | "image/webp" | "application/pdf";
export type Name1 = string;
export type Sha256 = string;
export type SizeBytes = number;
export type Kind1 = "link";
export type Label = string | null;
export type Url = string;
export type Attachments = (FileAttachment | LinkAttachment)[];
/**
 * @minItems 1
 */
export type Components = [LinearComponentV2, ...LinearComponentV2[]];
export type Attachments1 = (FileAttachment | LinkAttachment)[];
export type Description1 = string | null;
export type Id3 = string;
/**
 * @minItems 2
 */
export type StationIds = [string, string, ...string[]];
export type Description2 = string | null;
/**
 * @minItems 1
 */
export type Designs = [LayoutDesignV2, ...LayoutDesignV2[]];
export type Attachments2 = (FileAttachment | LinkAttachment)[];
export type BaseComponentIds = string[];
export type Description3 = string | null;
export type Id4 = string;
export type Title = string;
export type Id5 = string;
/**
 * @minItems 1
 */
export type Stations = [StationV2, ...StationV2[]];
export type Id6 = string;
export type Name2 = string;
export type Title1 = string;

export interface SingleRowFacilityLayoutConfigV2 {
  decision_model: DecisionModelV2;
  domain: SingleRowDomainRefV2;
  execution: ExecutionConfig;
  reporting?: LayoutReportingV2;
  schema_version: SchemaVersion;
  study: LayoutStudyV2;
}
export interface DecisionModelV2 {
  adjacency_flow?: AdjacencyFlow;
  rel_closeness?: RelMatrix | null;
  retained_compatible_layouts?: RetainedCompatibleLayouts;
  selected_objectives?: SelectedObjectives;
  undesired_prescribed_adjacencies?: UndesiredPrescribedAdjacencies;
}
export interface FlowMatrix {
  directed: Directed;
  entries: Entries;
  horizon: Horizon;
  provenance: Provenance;
  unit: Unit;
}
export interface FlowEntry {
  from_station_id: FromStationId;
  quantity: Quantity;
  to_station_id: ToStationId;
}
export interface AdjacencyValueMatrix {
  description: Description;
  directed: Directed1;
  direction: Direction;
  entries: Entries1;
  id: Id;
  name: Name;
  provenance: Provenance1;
  reference_period?: ReferencePeriod;
  unit: Unit1;
}
export interface AdjacencyValueEntry {
  from_station_id: FromStationId1;
  to_station_id: ToStationId1;
  value: Value;
}
export interface RelMatrix {
  requirements: Requirements;
}
export interface RelRequirement {
  first_station_id: FirstStationId;
  level: Level;
  provenance: Provenance2;
  reason: Reason;
  second_station_id: SecondStationId;
}
export interface ObjectiveReference {
  id: Id1;
  version: Version;
}
export interface UndesiredAdjacency {
  cause: Cause;
  explanation: Explanation;
  first_station_id: FirstStationId1;
  policy: Policy;
  provenance: Provenance3;
  second_station_id: SecondStationId1;
}
export interface SingleRowDomainRefV2 {
  id: Id2;
  version: Version1;
}
export interface ExecutionConfig {
  counting_convention: CountingConvention;
  integer_limits: IntegerLimits;
  methods: MethodsConfig;
  persistence: PersistenceConfig;
}
export interface IntegerLimits {
  cancellation_grace_ms: CancellationGraceMs;
  control_connect_timeout_ms: ControlConnectTimeoutMs;
  control_max_message_bytes: ControlMaxMessageBytes;
  control_response_timeout_ms: ControlResponseTimeoutMs;
  event_max_payload_bytes: EventMaxPayloadBytes;
  exact_timeout_ms: ExactTimeoutMs;
  input_max_bytes: InputMaxBytes;
  max_n: MaxN;
  reference_max_n: ReferenceMaxN;
  reference_timeout_ms: ReferenceTimeoutMs;
  runner_log_backup_count: RunnerLogBackupCount;
  runner_log_max_bytes: RunnerLogMaxBytes;
  worker_max_message_bytes: WorkerMaxMessageBytes;
}
export interface MethodsConfig {
  exact: ExactMethodConfig;
  reference: ReferenceMethodConfig;
}
export interface ExactMethodConfig {
  engine: Engine;
}
export interface ReferenceMethodConfig {
  engine: Engine1;
}
export interface PersistenceConfig {
  persist_events: PersistEvents;
  policy: Policy1;
}
export interface LayoutReportingV2 {
  invalid_combinations?: InvalidCombinations;
}
export interface LayoutStudyV2 {
  attachments?: Attachments;
  components: Components;
  description?: Description2;
  designs: Designs;
  id: Id5;
  stations: Stations;
  title: Title1;
}
export interface FileAttachment {
  kind: Kind;
  media_type: MediaType;
  name: Name1;
  sha256: Sha256;
  size_bytes: SizeBytes;
}
export interface LinkAttachment {
  kind: Kind1;
  label?: Label;
  url: Url;
}
export interface LinearComponentV2 {
  attachments?: Attachments1;
  description?: Description1;
  id: Id3;
  station_ids: StationIds;
}
export interface LayoutDesignV2 {
  attachments?: Attachments2;
  base_component_ids: BaseComponentIds;
  description?: Description3;
  id: Id4;
  title: Title;
}
export interface StationV2 {
  id: Id6;
  name: Name2;
}
