/* Generated from JSON Schema. Do not edit. */

export type GatewayMessage =
  | (
      | HelloRequest
      | PingRequest
      | ShutdownRequest
      | DomainsListRequest
      | LayoutDecisionCriteriaRequest
      | TemplatesListRequest
      | TemplatesLoadRequest
      | TemplatesSaveRequest
      | TemplatesSetForRunRequest
      | StudyValidateRequest
      | StudyPrepareRequest
      | LayoutValidateForestRequest
      | LayoutEstimateCombinationsRequest
      | DomainRunStartRequest
      | DomainRunCancelRequest
      | DomainRunResumeRequest
      | DomainRunStatusRequest
      | DomainRunListRequest
      | DomainRunDeleteRequest
      | DomainRunResultRequest
      | DomainRunCasePageRequest
      | DomainRunCaseDetailRequest
      | DomainRunDominatorsRequest
      | DomainRunFrontierRequest
      | DomainRunPlotPointsRequest
      | DomainRunPlotProjectionRequest
      | DomainRunMetricsRequest
      | AttachmentBeginRequest
      | AttachmentAppendRequest
      | AttachmentFinishRequest
      | AttachmentAbortRequest
      | AttachmentReadRequest
      | StudyDocumentationRequest
    )
  | GatewayResponse
  | (
      | GenerationStartedEvent
      | GenerationProgressEvent
      | CoreCaseStartedEvent
      | CoreProgressEvent
      | TerminalEvent
      | OperationErrorEvent
    );
export type Command = "hello";
export type MessageType = "request";
export type ProtocolVersion = "1.5";
export type RequestId = string;
export type Command1 = "ping";
export type MessageType1 = "request";
export type ProtocolVersion1 = "1.5";
export type RequestId1 = string;
export type Command2 = "shutdown";
export type MessageType2 = "request";
export type ProtocolVersion2 = "1.5";
export type RequestId2 = string;
export type Command3 = "domains.list";
export type MessageType3 = "request";
export type ProtocolVersion3 = "1.5";
export type RequestId3 = string;
export type Command4 = "layout.decision_criteria";
export type MessageType4 = "request";
export type ProtocolVersion4 = "1.5";
export type RequestId4 = string;
export type Command5 = "templates.list";
export type MessageType5 = "request";
export type ProtocolVersion5 = "1.5";
export type RequestId5 = string;
export type Command6 = "templates.load";
export type MessageType6 = "request";
export type TemplateId = string;
export type ProtocolVersion6 = "1.5";
export type RequestId6 = string;
export type Command7 = "templates.save";
export type MessageType7 = "request";
export type JsonValue = unknown;
export type ProtocolVersion7 = "1.5";
export type RequestId7 = string;
export type Command8 = "templates.set_for_run";
export type MessageType8 = "request";
export type DomainRunId = string;
export type Enabled = boolean;
export type ProtocolVersion8 = "1.5";
export type RequestId8 = string;
export type Command9 = "study.validate";
export type MessageType9 = "request";
export type ProtocolVersion9 = "1.5";
export type RequestId9 = string;
export type Command10 = "study.prepare";
export type MessageType10 = "request";
export type ProtocolVersion10 = "1.5";
export type RequestId10 = string;
export type Command11 = "layout.validate_forest";
export type MessageType11 = "request";
export type ProtocolVersion11 = "1.5";
export type RequestId11 = string;
export type Command12 = "layout.estimate_combinations";
export type MessageType12 = "request";
export type ProtocolVersion12 = "1.5";
export type RequestId12 = string;
export type Command13 = "domain_run.start";
export type MessageType13 = "request";
export type DomainExperimentId = string;
export type ProtocolVersion13 = "1.5";
export type RequestId13 = string;
export type Command14 = "domain_run.cancel";
export type MessageType14 = "request";
export type DomainRunId1 = string;
export type Reason = string | null;
export type ProtocolVersion14 = "1.5";
export type RequestId14 = string;
export type Command15 = "domain_run.resume";
export type MessageType15 = "request";
export type DomainRunId2 = string;
export type ProtocolVersion15 = "1.5";
export type RequestId15 = string;
export type Command16 = "domain_run.status";
export type MessageType16 = "request";
export type ProtocolVersion16 = "1.5";
export type RequestId16 = string;
export type Command17 = "domain_run.list";
export type MessageType17 = "request";
export type DomainExperimentId1 = string | null;
export type DomainId = string | null;
export type ProtocolVersion17 = "1.5";
export type RequestId17 = string;
export type Command18 = "domain_run.delete";
export type MessageType18 = "request";
export type ProtocolVersion18 = "1.5";
export type RequestId18 = string;
export type Command19 = "domain_run.result";
export type MessageType19 = "request";
export type ProtocolVersion19 = "1.5";
export type RequestId19 = string;
export type Command20 = "domain_run.case_page";
export type MessageType20 = "request";
export type DesignId = string;
export type Direction = "ascending" | "descending";
export type DomainRunId3 = string;
export type Order = string;
export type Page = number;
export type ProtocolVersion20 = "1.5";
export type RequestId20 = string;
export type Command21 = "domain_run.case_detail";
export type MessageType21 = "request";
export type CaseId = string;
export type DomainRunId4 = string;
export type EquivalentOffset = number;
export type ProtocolVersion21 = "1.5";
export type RequestId21 = string;
export type Command22 = "domain_run.dominators";
export type MessageType22 = "request";
export type CaseId1 = string;
export type Cursor = number;
export type DomainRunId5 = string;
export type ProtocolVersion22 = "1.5";
export type RequestId22 = string;
export type Command23 = "domain_run.frontier";
export type MessageType23 = "request";
export type Cursor1 = number;
export type DesignId1 = string;
export type DomainRunId6 = string;
export type ProtocolVersion23 = "1.5";
export type RequestId23 = string;
export type Command24 = "domain_run.plot_points";
export type MessageType24 = "request";
export type Cursor2 = number;
export type DesignId2 = string;
export type DomainRunId7 = string;
export type XObjectiveId = string;
export type YObjectiveId = string;
export type ProtocolVersion24 = "1.5";
export type RequestId24 = string;
export type Command25 = "domain_run.plot_projection";
export type MessageType25 = "request";
export type Cursor3 = number;
export type DesignId3 = string;
export type DomainRunId8 = string;
export type Level = 0 | 1 | 2;
export type Section = "groups" | "frontier_positions";
export type XLogK = number;
export type XObjectiveId1 = string;
export type XScale = "automatic" | "linear" | "square-root" | "adjusted-log" | "percentile";
export type YLogK = number;
export type YObjectiveId1 = string;
export type YScale = "automatic" | "linear" | "square-root" | "adjusted-log" | "percentile";
export type ProtocolVersion25 = "1.5";
export type RequestId25 = string;
export type Command26 = "domain_run.metrics";
export type MessageType26 = "request";
export type CaseId2 = string | null;
export type CriterionId = string | null;
export type Cursor4 = number;
export type DesignId4 = string | null;
export type DomainRunId9 = string;
export type MetricId = string;
export type ProtocolVersion26 = "1.5";
export type RequestId26 = string;
export type Command27 = "attachments.begin";
export type MessageType27 = "request";
export type MediaType = "image/png" | "image/jpeg" | "image/webp" | "application/pdf";
export type Name = string;
export type SizeBytes = number;
export type ProtocolVersion27 = "1.5";
export type RequestId27 = string;
export type Command28 = "attachments.append";
export type MessageType28 = "request";
export type Data = string;
export type Offset = number;
export type UploadId = string;
export type ProtocolVersion28 = "1.5";
export type RequestId28 = string;
export type Command29 = "attachments.finish";
export type MessageType29 = "request";
export type UploadId1 = string;
export type ProtocolVersion29 = "1.5";
export type RequestId29 = string;
export type Command30 = "attachments.abort";
export type MessageType30 = "request";
export type ProtocolVersion30 = "1.5";
export type RequestId30 = string;
export type Command31 = "attachments.read";
export type MessageType31 = "request";
export type Length = number;
export type Offset1 = number;
export type Sha256 = string;
export type ProtocolVersion31 = "1.5";
export type RequestId31 = string;
export type Command32 = "study.documentation";
export type MessageType32 = "request";
export type ProtocolVersion32 = "1.5";
export type RequestId32 = string;
export type Code = string;
export type Message = string;
export type MessageType33 = "response";
export type OperationId = string | null;
export type ProtocolVersion33 = "1.5";
export type RequestId33 = string;
export type Status = "success" | "accepted" | "error";
export type DomainRunId10 = string;
export type Total = number | string;
export type Event = "generation_started";
export type MessageType34 = "event";
export type OperationId1 = string;
export type ProtocolVersion34 = "1.5";
export type Sequence = number;
export type Completed = number | string;
export type DomainRunId11 = string;
export type Total1 = number | string;
export type ValidSelections = number | string | null;
export type Event1 = "generation_progress";
export type MessageType35 = "event";
export type OperationId2 = string;
export type ProtocolVersion35 = "1.5";
export type Sequence1 = number;
export type CoreRunId = string;
export type Description = string;
export type DesignId5 = string | null;
export type DomainRunId12 = string;
export type Ordinal = number;
export type Event2 = "core_case_started";
export type MessageType36 = "event";
export type OperationId3 = string;
export type ProtocolVersion36 = "1.5";
export type Sequence2 = number;
export type Completed1 = number;
export type CoreRunId1 = string;
export type DomainRunId13 = string;
export type Stage = string;
export type Total2 = number | null;
export type Event3 = "core_progress";
export type MessageType37 = "event";
export type OperationId4 = string;
export type ProtocolVersion37 = "1.5";
export type Sequence3 = number;
export type DomainRunId14 = string;
export type Status1 = "completed" | "failed" | "cancelled";
export type Event4 = "terminal";
export type MessageType38 = "event";
export type OperationId5 = string;
export type ProtocolVersion38 = "1.5";
export type Sequence4 = number;
export type DomainRunId15 = string | null;
export type Event5 = "error";
export type MessageType39 = "event";
export type OperationId6 = string;
export type ProtocolVersion39 = "1.5";
export type Sequence5 = number;

export interface HelloRequest {
  command: Command;
  message_type: MessageType;
  params: EmptyParams;
  protocol_version: ProtocolVersion;
  request_id: RequestId;
}
export interface EmptyParams {}
export interface PingRequest {
  command: Command1;
  message_type: MessageType1;
  params: EmptyParams;
  protocol_version: ProtocolVersion1;
  request_id: RequestId1;
}
export interface ShutdownRequest {
  command: Command2;
  message_type: MessageType2;
  params: EmptyParams;
  protocol_version: ProtocolVersion2;
  request_id: RequestId2;
}
export interface DomainsListRequest {
  command: Command3;
  message_type: MessageType3;
  params: EmptyParams;
  protocol_version: ProtocolVersion3;
  request_id: RequestId3;
}
export interface LayoutDecisionCriteriaRequest {
  command: Command4;
  message_type: MessageType4;
  params: EmptyParams;
  protocol_version: ProtocolVersion4;
  request_id: RequestId4;
}
export interface TemplatesListRequest {
  command: Command5;
  message_type: MessageType5;
  params: EmptyParams;
  protocol_version: ProtocolVersion5;
  request_id: RequestId5;
}
export interface TemplatesLoadRequest {
  command: Command6;
  message_type: MessageType6;
  params: TemplateParams;
  protocol_version: ProtocolVersion6;
  request_id: RequestId6;
}
export interface TemplateParams {
  template_id: TemplateId;
}
export interface TemplatesSaveRequest {
  command: Command7;
  message_type: MessageType7;
  params: DraftParams;
  protocol_version: ProtocolVersion7;
  request_id: RequestId7;
}
export interface DraftParams {
  draft: Draft;
}
export interface Draft {
  [k: string]: JsonValue;
}
export interface TemplatesSetForRunRequest {
  command: Command8;
  message_type: MessageType8;
  params: TemplateRunParams;
  protocol_version: ProtocolVersion8;
  request_id: RequestId8;
}
export interface TemplateRunParams {
  domain_run_id: DomainRunId;
  enabled: Enabled;
}
export interface StudyValidateRequest {
  command: Command9;
  message_type: MessageType9;
  params: DraftParams;
  protocol_version: ProtocolVersion9;
  request_id: RequestId9;
}
export interface StudyPrepareRequest {
  command: Command10;
  message_type: MessageType10;
  params: DraftParams;
  protocol_version: ProtocolVersion10;
  request_id: RequestId10;
}
export interface LayoutValidateForestRequest {
  command: Command11;
  message_type: MessageType11;
  params: DraftParams;
  protocol_version: ProtocolVersion11;
  request_id: RequestId11;
}
export interface LayoutEstimateCombinationsRequest {
  command: Command12;
  message_type: MessageType12;
  params: DraftParams;
  protocol_version: ProtocolVersion12;
  request_id: RequestId12;
}
export interface DomainRunStartRequest {
  command: Command13;
  message_type: MessageType13;
  params: ExperimentParams;
  protocol_version: ProtocolVersion13;
  request_id: RequestId13;
}
export interface ExperimentParams {
  domain_experiment_id: DomainExperimentId;
}
export interface DomainRunCancelRequest {
  command: Command14;
  message_type: MessageType14;
  params: CancelParams;
  protocol_version: ProtocolVersion14;
  request_id: RequestId14;
}
export interface CancelParams {
  domain_run_id: DomainRunId1;
  reason?: Reason;
}
export interface DomainRunResumeRequest {
  command: Command15;
  message_type: MessageType15;
  params: DomainRunParams;
  protocol_version: ProtocolVersion15;
  request_id: RequestId15;
}
export interface DomainRunParams {
  domain_run_id: DomainRunId2;
}
export interface DomainRunStatusRequest {
  command: Command16;
  message_type: MessageType16;
  params: DomainRunParams;
  protocol_version: ProtocolVersion16;
  request_id: RequestId16;
}
export interface DomainRunListRequest {
  command: Command17;
  message_type: MessageType17;
  params: RunListParams;
  protocol_version: ProtocolVersion17;
  request_id: RequestId17;
}
export interface RunListParams {
  domain_experiment_id?: DomainExperimentId1;
  domain_id?: DomainId;
}
export interface DomainRunDeleteRequest {
  command: Command18;
  message_type: MessageType18;
  params: DomainRunParams;
  protocol_version: ProtocolVersion18;
  request_id: RequestId18;
}
export interface DomainRunResultRequest {
  command: Command19;
  message_type: MessageType19;
  params: DomainRunParams;
  protocol_version: ProtocolVersion19;
  request_id: RequestId19;
}
export interface DomainRunCasePageRequest {
  command: Command20;
  message_type: MessageType20;
  params: DomainCasePageParams;
  protocol_version: ProtocolVersion20;
  request_id: RequestId20;
}
export interface DomainCasePageParams {
  design_id: DesignId;
  direction?: Direction;
  domain_run_id: DomainRunId3;
  order: Order;
  page: Page;
}
export interface DomainRunCaseDetailRequest {
  command: Command21;
  message_type: MessageType21;
  params: DomainCaseDetailParams;
  protocol_version: ProtocolVersion21;
  request_id: RequestId21;
}
export interface DomainCaseDetailParams {
  case_id: CaseId;
  domain_run_id: DomainRunId4;
  equivalent_offset?: EquivalentOffset;
}
export interface DomainRunDominatorsRequest {
  command: Command22;
  message_type: MessageType22;
  params: DomainDominatorsParams;
  protocol_version: ProtocolVersion22;
  request_id: RequestId22;
}
export interface DomainDominatorsParams {
  case_id: CaseId1;
  cursor?: Cursor;
  domain_run_id: DomainRunId5;
}
export interface DomainRunFrontierRequest {
  command: Command23;
  message_type: MessageType23;
  params: DomainFrontierParams;
  protocol_version: ProtocolVersion23;
  request_id: RequestId23;
}
export interface DomainFrontierParams {
  cursor?: Cursor1;
  design_id: DesignId1;
  domain_run_id: DomainRunId6;
}
export interface DomainRunPlotPointsRequest {
  command: Command24;
  message_type: MessageType24;
  params: DomainPlotPointsParams;
  protocol_version: ProtocolVersion24;
  request_id: RequestId24;
}
export interface DomainPlotPointsParams {
  cursor?: Cursor2;
  design_id: DesignId2;
  domain_run_id: DomainRunId7;
  x_objective_id: XObjectiveId;
  y_objective_id: YObjectiveId;
}
export interface DomainRunPlotProjectionRequest {
  command: Command25;
  message_type: MessageType25;
  params: DomainPlotProjectionParams;
  protocol_version: ProtocolVersion25;
  request_id: RequestId25;
}
export interface DomainPlotProjectionParams {
  cursor?: Cursor3;
  design_id: DesignId3;
  domain_run_id: DomainRunId8;
  level: Level;
  section: Section;
  x_log_k?: XLogK;
  x_objective_id: XObjectiveId1;
  x_scale: XScale;
  y_log_k?: YLogK;
  y_objective_id: YObjectiveId1;
  y_scale: YScale;
}
export interface DomainRunMetricsRequest {
  command: Command26;
  message_type: MessageType26;
  params: DomainRunMetricsParams;
  protocol_version: ProtocolVersion26;
  request_id: RequestId26;
}
export interface DomainRunMetricsParams {
  case_id?: CaseId2;
  criterion_id?: CriterionId;
  cursor?: Cursor4;
  design_id?: DesignId4;
  domain_run_id: DomainRunId9;
  metric_id: MetricId;
}
export interface AttachmentBeginRequest {
  command: Command27;
  message_type: MessageType27;
  params: AttachmentBeginParams;
  protocol_version: ProtocolVersion27;
  request_id: RequestId27;
}
export interface AttachmentBeginParams {
  media_type: MediaType;
  name: Name;
  size_bytes: SizeBytes;
}
export interface AttachmentAppendRequest {
  command: Command28;
  message_type: MessageType28;
  params: AttachmentAppendParams;
  protocol_version: ProtocolVersion28;
  request_id: RequestId28;
}
export interface AttachmentAppendParams {
  data: Data;
  offset: Offset;
  upload_id: UploadId;
}
export interface AttachmentFinishRequest {
  command: Command29;
  message_type: MessageType29;
  params: AttachmentTransferParams;
  protocol_version: ProtocolVersion29;
  request_id: RequestId29;
}
export interface AttachmentTransferParams {
  upload_id: UploadId1;
}
export interface AttachmentAbortRequest {
  command: Command30;
  message_type: MessageType30;
  params: AttachmentTransferParams;
  protocol_version: ProtocolVersion30;
  request_id: RequestId30;
}
export interface AttachmentReadRequest {
  command: Command31;
  message_type: MessageType31;
  params: AttachmentReadParams;
  protocol_version: ProtocolVersion31;
  request_id: RequestId31;
}
export interface AttachmentReadParams {
  length: Length;
  offset: Offset1;
  sha256: Sha256;
}
export interface StudyDocumentationRequest {
  command: Command32;
  message_type: MessageType32;
  params: ExperimentParams;
  protocol_version: ProtocolVersion32;
  request_id: RequestId32;
}
export interface GatewayResponse {
  error: GatewayError | null;
  message_type?: MessageType33;
  operation_id: OperationId;
  protocol_version?: ProtocolVersion33;
  request_id: RequestId33;
  result: unknown;
  status: Status;
}
export interface GatewayError {
  code: Code;
  details: Details;
  message: Message;
}
export interface Details {
  [k: string]: JsonValue;
}
export interface GenerationStartedEvent {
  data: GenerationStartedData;
  event: Event;
  message_type?: MessageType34;
  operation_id: OperationId1;
  protocol_version?: ProtocolVersion34;
  sequence: Sequence;
}
export interface GenerationStartedData {
  domain_run_id: DomainRunId10;
  total: Total;
}
export interface GenerationProgressEvent {
  data: GenerationProgressData;
  event: Event1;
  message_type?: MessageType35;
  operation_id: OperationId2;
  protocol_version?: ProtocolVersion35;
  sequence: Sequence1;
}
export interface GenerationProgressData {
  completed: Completed;
  domain_run_id: DomainRunId11;
  total: Total1;
  valid_selections?: ValidSelections;
}
export interface CoreCaseStartedEvent {
  data: CoreCaseStartedData;
  event: Event2;
  message_type?: MessageType36;
  operation_id: OperationId3;
  protocol_version?: ProtocolVersion36;
  sequence: Sequence2;
}
export interface CoreCaseStartedData {
  core_run_id: CoreRunId;
  description: Description;
  design_id?: DesignId5;
  domain_run_id: DomainRunId12;
  ordinal: Ordinal;
}
export interface CoreProgressEvent {
  data: CoreProgressData;
  event: Event3;
  message_type?: MessageType37;
  operation_id: OperationId4;
  protocol_version?: ProtocolVersion37;
  sequence: Sequence3;
}
export interface CoreProgressData {
  completed: Completed1;
  core_run_id: CoreRunId1;
  domain_run_id: DomainRunId13;
  stage: Stage;
  total: Total2;
}
export interface TerminalEvent {
  data: TerminalData;
  event: Event4;
  message_type?: MessageType38;
  operation_id: OperationId5;
  protocol_version?: ProtocolVersion38;
  sequence: Sequence4;
}
export interface TerminalData {
  domain_run_id: DomainRunId14;
  status: Status1;
}
export interface OperationErrorEvent {
  data: OperationErrorData;
  event: Event5;
  message_type?: MessageType39;
  operation_id: OperationId6;
  protocol_version?: ProtocolVersion39;
  sequence: Sequence5;
}
export interface OperationErrorData {
  domain_run_id: DomainRunId15;
  error: GatewayError;
}
