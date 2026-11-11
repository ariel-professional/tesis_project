/* Generated from JSON Schema. Do not edit. */

export type Id = "single-row-facility-layout";
export type Version = "1.0.0";
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
export type Policy = "normal" | "debug";
export type InvalidCombinations = "summary" | "full";
export type SchemaVersion = "1.0.0";
export type Kind = "file";
export type MediaType = "image/png" | "image/jpeg" | "image/webp" | "application/pdf";
export type Name = string;
export type Sha256 = string;
export type SizeBytes = number;
export type Kind1 = "link";
export type Label = string | null;
export type Url = string;
export type Attachments = (FileAttachment | LinkAttachment)[];
/**
 * @minItems 1
 */
export type Components = [LinearComponent, ...LinearComponent[]];
export type Attachments1 = (FileAttachment | LinkAttachment)[];
export type Description = string | null;
export type Id1 = string;
/**
 * @minItems 2
 */
export type StationIds = [string, string, ...string[]];
export type Utility = number;
export type Description1 = string | null;
/**
 * @minItems 1
 */
export type Designs = [LayoutDesign, ...LayoutDesign[]];
export type Attachments2 = (FileAttachment | LinkAttachment)[];
/**
 * @minItems 1
 */
export type BaseComponentIds = [string, ...string[]];
export type Description2 = string | null;
export type Id2 = string;
export type Title = string;
export type Id3 = string;
/**
 * @minItems 1
 */
export type Stations = [Station, ...Station[]];
export type Id4 = string;
export type Name1 = string;
export type Title1 = string;

export interface SingleRowFacilityLayoutConfig {
  domain: SingleRowDomainRef;
  execution: ExecutionConfig;
  reporting: LayoutReporting;
  schema_version: SchemaVersion;
  study: LayoutStudy;
}
export interface SingleRowDomainRef {
  id: Id;
  version: Version;
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
  policy: Policy;
}
export interface LayoutReporting {
  invalid_combinations: InvalidCombinations;
}
export interface LayoutStudy {
  attachments?: Attachments;
  components: Components;
  description?: Description1;
  designs: Designs;
  id: Id3;
  stations: Stations;
  title: Title1;
}
export interface FileAttachment {
  kind: Kind;
  media_type: MediaType;
  name: Name;
  sha256: Sha256;
  size_bytes: SizeBytes;
}
export interface LinkAttachment {
  kind: Kind1;
  label?: Label;
  url: Url;
}
export interface LinearComponent {
  attachments?: Attachments1;
  description?: Description;
  id: Id1;
  station_ids: StationIds;
  utility: Utility;
}
export interface LayoutDesign {
  attachments?: Attachments2;
  base_component_ids: BaseComponentIds;
  description?: Description2;
  id: Id2;
  title: Title;
}
export interface Station {
  id: Id4;
  name: Name1;
}
