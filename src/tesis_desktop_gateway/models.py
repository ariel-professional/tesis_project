from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, JsonValue, model_validator

from tesis_domain_extensions.contracts.common import (
    DomainExperimentId,
    NonNegativeInt,
    NormalizedText,
    RunId,
    StrictModel,
)
from tesis_domain_extensions.contracts.evidence import MediaType

GatewayCommand = Literal[
    "attachments.begin",
    "attachments.append",
    "attachments.finish",
    "attachments.abort",
    "attachments.read",
    "study.documentation",
    "hello",
    "ping",
    "shutdown",
    "domains.list",
    "layout.decision_criteria",
    "templates.list",
    "templates.load",
    "templates.save",
    "templates.set_for_run",
    "study.validate",
    "study.prepare",
    "layout.validate_forest",
    "layout.estimate_combinations",
    "domain_run.start",
    "domain_run.cancel",
    "domain_run.resume",
    "domain_run.status",
    "domain_run.list",
    "domain_run.delete",
    "domain_run.result",
    "domain_run.case_page",
    "domain_run.case_detail",
    "domain_run.dominators",
    "domain_run.frontier",
    "domain_run.plot_points",
    "domain_run.plot_projection",
    "domain_run.metrics",
]


class EmptyParams(StrictModel):
    pass


class DraftParams(StrictModel):
    draft: dict[str, JsonValue]


class TemplateParams(StrictModel):
    template_id: str


class ExperimentParams(StrictModel):
    domain_experiment_id: str


class DomainRunParams(StrictModel):
    domain_run_id: RunId


class TemplateRunParams(DomainRunParams):
    enabled: bool


class CancelParams(DomainRunParams):
    reason: str | None = Field(default=None, max_length=512)


class RunListParams(StrictModel):
    domain_experiment_id: str | None = None
    domain_id: str | None = None


class DomainCasePageParams(DomainRunParams):
    design_id: str
    order: str
    direction: Literal["ascending", "descending"] = "ascending"
    page: NonNegativeInt


class DomainCaseDetailParams(DomainRunParams):
    case_id: DomainExperimentId
    equivalent_offset: NonNegativeInt = 0


class DomainFrontierParams(DomainRunParams):
    design_id: str
    cursor: NonNegativeInt = 0


class DomainDominatorsParams(DomainRunParams):
    case_id: DomainExperimentId
    cursor: NonNegativeInt = 0


class DomainPlotPointsParams(DomainRunParams):
    design_id: str
    x_objective_id: str
    y_objective_id: str
    cursor: NonNegativeInt = 0


class DomainPlotProjectionParams(DomainRunParams):
    design_id: str
    x_objective_id: str
    y_objective_id: str
    x_scale: Literal["automatic", "linear", "square-root", "adjusted-log", "percentile"]
    y_scale: Literal["automatic", "linear", "square-root", "adjusted-log", "percentile"]
    x_log_k: float = Field(default=100, gt=0, allow_inf_nan=False)
    y_log_k: float = Field(default=100, gt=0, allow_inf_nan=False)
    level: Literal[0, 1, 2]
    section: Literal["groups", "frontier_positions"]
    cursor: NonNegativeInt = 0


class DomainRunMetricsParams(DomainRunParams):
    metric_id: str
    design_id: str | None = None
    criterion_id: str | None = None
    case_id: str | None = None
    cursor: NonNegativeInt = 0


class AttachmentBeginParams(StrictModel):
    name: NormalizedText
    media_type: MediaType
    size_bytes: NonNegativeInt


class AttachmentTransferParams(StrictModel):
    upload_id: RunId


class AttachmentAppendParams(AttachmentTransferParams):
    offset: NonNegativeInt
    data: Annotated[str, Field(max_length=699052)]


class AttachmentReadParams(StrictModel):
    sha256: DomainExperimentId
    offset: NonNegativeInt
    length: Annotated[NonNegativeInt, Field(le=524288)]


class RequestBase(StrictModel):
    protocol_version: Literal["1.5"]
    message_type: Literal["request"]
    request_id: RunId


class HelloRequest(RequestBase):
    command: Literal["hello"]
    params: EmptyParams


class PingRequest(RequestBase):
    command: Literal["ping"]
    params: EmptyParams


class ShutdownRequest(RequestBase):
    command: Literal["shutdown"]
    params: EmptyParams


class DomainsListRequest(RequestBase):
    command: Literal["domains.list"]
    params: EmptyParams


class LayoutDecisionCriteriaRequest(RequestBase):
    command: Literal["layout.decision_criteria"]
    params: EmptyParams


class TemplatesListRequest(RequestBase):
    command: Literal["templates.list"]
    params: EmptyParams


class TemplatesLoadRequest(RequestBase):
    command: Literal["templates.load"]
    params: TemplateParams


class TemplatesSaveRequest(RequestBase):
    command: Literal["templates.save"]
    params: DraftParams


class TemplatesSetForRunRequest(RequestBase):
    command: Literal["templates.set_for_run"]
    params: TemplateRunParams


class StudyValidateRequest(RequestBase):
    command: Literal["study.validate"]
    params: DraftParams


class StudyPrepareRequest(RequestBase):
    command: Literal["study.prepare"]
    params: DraftParams


class LayoutValidateForestRequest(RequestBase):
    command: Literal["layout.validate_forest"]
    params: DraftParams


class LayoutEstimateCombinationsRequest(RequestBase):
    command: Literal["layout.estimate_combinations"]
    params: DraftParams


class DomainRunStartRequest(RequestBase):
    command: Literal["domain_run.start"]
    params: ExperimentParams


class DomainRunCancelRequest(RequestBase):
    command: Literal["domain_run.cancel"]
    params: CancelParams


class DomainRunResumeRequest(RequestBase):
    command: Literal["domain_run.resume"]
    params: DomainRunParams


class DomainRunStatusRequest(RequestBase):
    command: Literal["domain_run.status"]
    params: DomainRunParams


class DomainRunListRequest(RequestBase):
    command: Literal["domain_run.list"]
    params: RunListParams


class DomainRunDeleteRequest(RequestBase):
    command: Literal["domain_run.delete"]
    params: DomainRunParams


class DomainRunResultRequest(RequestBase):
    command: Literal["domain_run.result"]
    params: DomainRunParams


class DomainRunCasePageRequest(RequestBase):
    command: Literal["domain_run.case_page"]
    params: DomainCasePageParams


class DomainRunCaseDetailRequest(RequestBase):
    command: Literal["domain_run.case_detail"]
    params: DomainCaseDetailParams


class DomainRunDominatorsRequest(RequestBase):
    command: Literal["domain_run.dominators"]
    params: DomainDominatorsParams


class DomainRunFrontierRequest(RequestBase):
    command: Literal["domain_run.frontier"]
    params: DomainFrontierParams


class DomainRunPlotPointsRequest(RequestBase):
    command: Literal["domain_run.plot_points"]
    params: DomainPlotPointsParams


class DomainRunPlotProjectionRequest(RequestBase):
    command: Literal["domain_run.plot_projection"]
    params: DomainPlotProjectionParams


class DomainRunMetricsRequest(RequestBase):
    command: Literal["domain_run.metrics"]
    params: DomainRunMetricsParams


class AttachmentBeginRequest(RequestBase):
    command: Literal["attachments.begin"]
    params: AttachmentBeginParams


class AttachmentAppendRequest(RequestBase):
    command: Literal["attachments.append"]
    params: AttachmentAppendParams


class AttachmentFinishRequest(RequestBase):
    command: Literal["attachments.finish"]
    params: AttachmentTransferParams


class AttachmentAbortRequest(RequestBase):
    command: Literal["attachments.abort"]
    params: AttachmentTransferParams


class AttachmentReadRequest(RequestBase):
    command: Literal["attachments.read"]
    params: AttachmentReadParams


class StudyDocumentationRequest(RequestBase):
    command: Literal["study.documentation"]
    params: ExperimentParams


GatewayRequest = Annotated[
    HelloRequest
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
    | StudyDocumentationRequest,
    Field(discriminator="command"),
]


class GatewayError(StrictModel):
    code: str
    message: str
    details: dict[str, JsonValue]


class GatewayResponse(StrictModel):
    protocol_version: Literal["1.5"] = "1.5"
    message_type: Literal["response"] = "response"
    request_id: RunId
    status: Literal["success", "accepted", "error"]
    operation_id: RunId | None
    result: JsonValue | None
    error: GatewayError | None

    @model_validator(mode="after")
    def validate_outcome(self) -> GatewayResponse:
        if self.status == "error" and self.error is None:
            raise ValueError("error responses require an error")
        if self.status != "error" and self.error is not None:
            raise ValueError("successful responses cannot include an error")
        if self.status == "accepted" and self.operation_id is None:
            raise ValueError("accepted responses require an operation_id")
        return self


class GenerationStartedData(StrictModel):
    domain_run_id: RunId
    total: int | str


class GenerationProgressData(StrictModel):
    domain_run_id: RunId
    completed: int | str
    total: int | str
    valid_selections: int | str | None = None


class CoreCaseStartedData(StrictModel):
    domain_run_id: RunId
    ordinal: int = Field(ge=1)
    description: str
    core_run_id: RunId
    design_id: str | None = None


class CoreProgressData(StrictModel):
    domain_run_id: RunId
    core_run_id: RunId
    stage: str
    completed: int
    total: int | None


class TerminalData(StrictModel):
    domain_run_id: RunId
    status: Literal["completed", "failed", "cancelled"]


class OperationErrorData(StrictModel):
    domain_run_id: RunId | None
    error: GatewayError


class EventBase(StrictModel):
    protocol_version: Literal["1.5"] = "1.5"
    message_type: Literal["event"] = "event"
    operation_id: RunId
    sequence: int = Field(ge=1)


class GenerationStartedEvent(EventBase):
    event: Literal["generation_started"]
    data: GenerationStartedData


class GenerationProgressEvent(EventBase):
    event: Literal["generation_progress"]
    data: GenerationProgressData


class CoreCaseStartedEvent(EventBase):
    event: Literal["core_case_started"]
    data: CoreCaseStartedData


class CoreProgressEvent(EventBase):
    event: Literal["core_progress"]
    data: CoreProgressData


class TerminalEvent(EventBase):
    event: Literal["terminal"]
    data: TerminalData


class OperationErrorEvent(EventBase):
    event: Literal["error"]
    data: OperationErrorData


GatewayEvent = Annotated[
    GenerationStartedEvent
    | GenerationProgressEvent
    | CoreCaseStartedEvent
    | CoreProgressEvent
    | TerminalEvent
    | OperationErrorEvent,
    Field(discriminator="event"),
]
GatewayMessage = GatewayRequest | GatewayResponse | GatewayEvent
